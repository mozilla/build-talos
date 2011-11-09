# ***** BEGIN LICENSE BLOCK *****
# Version: MPL 1.1/GPL 2.0/LGPL 2.1
#
# The contents of this file are subject to the Mozilla Public License Version
# 1.1 (the "License"); you may not use this file except in compliance with
# the License. You may obtain a copy of the License at
# http://www.mozilla.org/MPL/
#
# Software distributed under the License is distributed on an "AS IS" basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License
# for the specific language governing rights and limitations under the
# License.
#
# The Original Code is standalone Firefox Windows performance test.
#
# The Initial Developer of the Original Code is Google Inc.
# Portions created by the Initial Developer are Copyright (C) 2006
# the Initial Developer. All Rights Reserved.
#
# Contributor(s):
#   Annie Sullivan <annie.sullivan@gmail.com> (original author)
#
# Alternatively, the contents of this file may be used under the terms of
# either the GNU General Public License Version 2 or later (the "GPL"), or
# the GNU Lesser General Public License Version 2.1 or later (the "LGPL"),
# in which case the provisions of the GPL or the LGPL are applicable instead
# of those above. If you wish to allow use of your version of this file only
# under the terms of either the GPL or the LGPL, and not to allow others to
# use your version of this file under the terms of the MPL, indicate your
# decision by deleting the provisions above and replace them with the notice
# and other provisions required by the GPL or the LGPL. If you do not delete
# the provisions above, a recipient may use your version of this file under
# the terms of any one of the MPL, the GPL or the LGPL.
#
# ***** END LICENSE BLOCK *****

"""A set of functions for process management on Windows.
"""

__author__ = 'annie.sullivan@gmail.com (Annie Sullivan)'



import platform
import os
import re
import time
import subprocess
from utils import talosError
import utils

class FFProcess(object):
    testAgent = None
    
    def __init__(self):
        pass

    def checkBrowserAlive(self, process_name):
        #is the browser actually up?
        return (self.ProcessesWithNames(process_name) and
                not self.ProcessesWithNames("crashreporter", "talkback", "dwwin"))

    def checkAllProcesses(self, process_name, child_process):
        #is anything browser related active?
        return self.ProcessesWithNames(process_name, child_process, "crashreporter", "talkback", "dwwin")

    def cleanupProcesses(self, process_name, child_process, browser_wait):
        #kill any remaining browser processes
        #returns string of which process_names were terminated and with what signal
        terminate_result = ''
        terminate_result = self.TerminateAllProcesses(browser_wait, process_name, child_process, "crashreporter", "dwwin", "talkback")
        #check if anything is left behind
        if self.checkAllProcesses(process_name, child_process):
            #this is for windows machines.  when attempting to send kill messages to win processes the OS
            # always gives the process a chance to close cleanly before terminating it, this takes longer
            # and we need to give it a little extra time to complete
            time.sleep(browser_wait)
            if self.checkAllProcesses(process_name, child_process):
                raise talosError("failed to cleanup")

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
        if 'url_mod' in test_config:
            browser_config['url_mod'] = test_config['url_mod']
            bcontroller_vars.append('url_mod')

        if (('xperf_providers' in test_config) and 
           ('xperf_stackwalk' in test_config)):
            print "extending with xperf!"
            browser_config['xperf_providers'] = test_config['xperf_providers']
            browser_config['xperf_stackwalk'] = test_config['xperf_stackwalk']
            bcontroller_vars.extend(['xperf_providers', 'xperf_stackwalk'])

        content = utils.writeConfigFile(browser_config, bcontroller_vars)

        fhandle = open(browser_config['bcontroller_config'], "w")
        fhandle.write(content)
        fhandle.close()

        return 'python bcontroller.py --configFile %s' % (browser_config['bcontroller_config'])

        return terminate_result

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

#user_pref("network.proxy.type", 1);
#user_pref("network.proxy.http", "%(host)s");
#user_pref("network.proxy.http_port", %(port)d);

