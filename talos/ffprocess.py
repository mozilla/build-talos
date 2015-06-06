# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Firefox process management for Talos"""

import mozfile
import os
import shutil
import time
import utils
import copy
from utils import TalosError, MakeDirectoryContentsWritable


class FFProcess(object):
    testAgent = None
    extra_prog = ["crashreporter"]  # list of extra programs to be killed

    def TerminateProcesses(self, pids, timeout):
        """Helper function to terminate processes with the given pids

        Args:
            pids: A list containing PIDs of process, i.e. firefox
        """
        results = []
        for pid in copy.deepcopy(pids):
            ret = self._TerminateProcess(pid, timeout)
            if ret:
                results.append("(%s): %s" % (pid, ret))
            else:
                # Remove PIDs which are already terminated
                pids.remove(pid)
        return ",".join(results)

    def checkProcesses(self, pids):
        """Returns a list of browser related PIDs still running

        Args:
            pids: A list containg PIDs
        Returns:
            A list containing PIDs which are still running
        """
        pids = [pid for pid in pids if utils.is_running(pid)]
        return pids

    def cleanupProcesses(self, pids, browser_wait):
        # kill any remaining browser processes
        # returns string of which process_names were terminated and with
        # what signal

        utils.debug("Terminating: %s", ", ".join(str(pid) for pid in pids))
        terminate_result = self.TerminateProcesses(pids, browser_wait)
        # check if anything is left behind
        if self.checkProcesses(pids):
            # this is for windows machines.  when attempting to send kill
            # messages to win processes the OS
            # always gives the process a chance to close cleanly before
            # terminating it, this takes longer
            # and we need to give it a little extra time to complete
            time.sleep(browser_wait)
            process_pids = self.checkProcesses(pids)
            if process_pids:
                raise TalosError(
                    "failed to cleanup process with PID: %s" % process_pids)

        return terminate_result

    def addRemoteServerPref(self, profile_dir, server):
        """
          edit the user.js in the profile (on the host machine) and
          add the xpconnect priviledges for the remote server
        """
        import urlparse
        user_js_filename = os.path.join(profile_dir, 'user.js')

        # NOTE: this should be sufficient for defining a docroot
        scheme = "http://"
        if (server.startswith('http://') or
            server.startswith('chrome://') or
            server.startswith('file:///')):  # noqa

            scheme = ""
        elif (server.find('://') >= 0):
            raise TalosError(
                "Unable to parse user defined webserver: '%s'" % (server))

        url = urlparse.urlparse('%s%s' % (scheme, server))

        port = url.port
        if not url.port or port < 0:
            port = 80

        # TODO: p2 is hardcoded, how do we determine what prefs.js
        # has hardcoded?
        remoteCode = """
user_pref("capability.principal.codebase.p2.granted", \
"UniversalPreferencesWrite UniversalXPConnect UniversalPreferencesRead");
user_pref("capability.principal.codebase.p2.id", "http://%(server)s");
user_pref("capability.principal.codebase.p2.subjectName", "");
""" % {"server": server, "host": url.hostname, "port": int(port)}
        with open(user_js_filename, 'a+') as user_js_file:
            user_js_file.write(remoteCode)

    # functions for dealing with files
    # these should really go in mozfile:
    # https://bugzilla.mozilla.org/show_bug.cgi?id=774916
    # These really don't have anything to do with process management

    def copyFile(self, fromfile, toDir):
        if not os.path.isfile(os.path.join(toDir, os.path.basename(fromfile))):
            shutil.copy(fromfile, toDir)
            utils.debug("installed %s", fromfile)
        else:
            utils.debug("WARNING: file already installed (%s)", fromfile)

    def removeDirectory(self, dir):
        MakeDirectoryContentsWritable(dir)
        mozfile.rmtree(dir)

    def getFile(self, handle, localFile=""):
        if os.path.isfile(handle):
            with open(handle, "r") as results_file:
                return results_file.read()
