# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Firefox process management for Talos"""

import os
import shutil
import sys
import time
import utils
from utils import talosError,MakeDirectoryContentsWritable

class FFProcess(object):
    testAgent = None
    extra_prog=["crashreporter"] #list of extra programs to be killed

    def ProcessesWithNames(self, *process_names):
        """Returns a list of processes running with the given name(s):
        [(pid, name), (...), ...]
        Useful to check whether a Browser process is still running

        Args:
            process_names: String or strings containing process names, i.e. "firefox"

        Returns:
            An array with a list of processes in the list which are running
        """

        processes_with_names = []
        for process_name in process_names:
            pids = self.GetPidsByName(process_name)
            if len(pids) > 0:
                processes_with_names.extend([(pid, process_name) for pid in pids])
        return processes_with_names


    def checkAllProcesses(self, process_name, child_process):
        #is anything browser related active?
        return self.ProcessesWithNames(*([process_name, child_process]+self.extra_prog))

    def cleanupProcesses(self, process_name, child_process, browser_wait):
        #kill any remaining browser processes
        #returns string of which process_names were terminated and with what signal
        processes_to_kill = filter(lambda n: n, ([process_name, child_process] +
                                                 self.extra_prog))
        utils.debug("Terminating: %s", ", ".join(str(p) for p in processes_to_kill))
        terminate_result = self.TerminateAllProcesses(browser_wait, *processes_to_kill)
        #check if anything is left behind
        if self.checkAllProcesses(process_name, child_process):
            #this is for windows machines.  when attempting to send kill messages to win processes the OS
            # always gives the process a chance to close cleanly before terminating it, this takes longer
            # and we need to give it a little extra time to complete
            time.sleep(browser_wait)
            processes = self.checkAllProcesses(process_name, child_process)
            if processes:
                raise talosError("failed to cleanup processes: %s" % processes)

        return terminate_result

    def GenerateBControllerCommandLine(self, command_line, browser_config, test_config):
        bcontroller_vars = ['command', 'child_process', 'process', 'browser_wait', 'test_timeout', 'browser_log']

        if 'xperf_path' in browser_config:
            bcontroller_vars.append('xperf_path')
            bcontroller_vars.extend(['buildid', 'sourcestamp', 'repository', 'title'])
            if 'name' in test_config:
              bcontroller_vars.append('testname')
              browser_config['testname'] = test_config['name']

        if (browser_config['webserver'] != 'localhost'):
            bcontroller_vars.extend(['host', 'port', 'deviceroot', 'env'])

        browser_config['command'] = command_line
        if 'url_timestamp' in test_config:
            browser_config['url_timestamp'] = test_config['url_timestamp']
            bcontroller_vars.append('url_timestamp')

        if (('xperf_providers' in test_config) and
            ('xperf_user_providers' in test_config) and
            ('xperf_stackwalk' in test_config)):
            print "extending with xperf!"
            browser_config['xperf_providers'] = test_config['xperf_providers']
            browser_config['xperf_user_providers'] = test_config['xperf_user_providers']
            browser_config['xperf_stackwalk'] = test_config['xperf_stackwalk']
            bcontroller_vars.extend(['xperf_providers', 'xperf_user_providers', 'xperf_stackwalk'])

        content = utils.writeConfigFile(browser_config, bcontroller_vars)

        fhandle = open(browser_config['bcontroller_config'], "w")
        fhandle.write(content)
        fhandle.close()

        here = os.path.dirname(os.path.realpath(__file__))
        return [sys.executable, os.path.join(here, 'bcontroller.py'),
                '--configFile', browser_config['bcontroller_config']]

    def addRemoteServerPref(self, profile_dir, server):
        """
          edit the user.js in the profile (on the host machine) and
          add the xpconnect priviledges for the remote server
        """
        import urlparse
        user_js_filename = os.path.join(profile_dir, 'user.js')
        user_js_file = open(user_js_filename, 'a+')

        #NOTE: this should be sufficient for defining a docroot
        scheme = "http://"
        if (server.startswith('http://') or
            server.startswith('chrome://') or
            server.startswith('file:///')):
          scheme = ""
        elif (server.find('://') >= 0):
          raise talosError("Unable to parse user defined webserver: '%s'" % (server))

        url = urlparse.urlparse('%s%s' % (scheme, server))

        port = url.port
        if not url.port or port < 0:
          port = 80

        #TODO: p2 is hardcoded, how do we determine what prefs.js has hardcoded?
        remoteCode = """
user_pref("capability.principal.codebase.p2.granted", "UniversalPreferencesWrite UniversalXPConnect UniversalPreferencesRead");
user_pref("capability.principal.codebase.p2.id", "http://%(server)s");
user_pref("capability.principal.codebase.p2.subjectName", "");
""" % { "server": server, "host": url.hostname, "port": int(port) }
        user_js_file.write(remoteCode)
        user_js_file.close()

    ### functions for dealing with files
    ### these should really go in mozfile:
    ### https://bugzilla.mozilla.org/show_bug.cgi?id=774916
    ### These really don't have anything to do with process management

    def copyFile(self, fromfile, toDir):
        if not os.path.isfile(os.path.join(toDir, os.path.basename(fromfile))):
            shutil.copy(fromfile, toDir)
            utils.debug("installed %s", fromfile)
        else:
            utils.debug("WARNING: file already installed (%s)", fromfile)

    def removeDirectory(self, dir):
        MakeDirectoryContentsWritable(dir)
        shutil.rmtree(dir)


    def getFile(self, handle, localFile=""):
        fileData = ''
        if os.path.isfile(handle):
            results_file = open(handle, "r")
            fileData = results_file.read()
            results_file.close()
        return fileData
