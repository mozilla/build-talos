# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import subprocess
import signal
import os
from select import select
import time
from ffprocess import FFProcess
import shutil
import utils


class LinuxProcess(FFProcess):

    def GenerateBrowserCommandLine(self, browser_path, extra_args, deviceroot, profile_dir, url):
        """Generates the command line for a process to run Browser

        Args:
            browser_path: String containing the path to the browser to use
            profile_dir: String containing the directory of the profile to run Browser in
            url: String containing url to start with.
        """

        profile_arg = ''
        if profile_dir:
            profile_arg = '-profile %s' % profile_dir

        cmd = '%s %s %s %s' % (browser_path,
                               extra_args,
                               profile_arg,
                               url)
        return cmd


    def _GetPidsByName(self, process_name):
        """Searches for processes containing a given string.

        Args:
            process_name: The string to be searched for

        Returns:
            A list of PIDs containing the string. An empty list is returned if none are
            found.
        """
        processes = utils.running_processes(process_name)
        return [pid for pid,_ in processes]

    def _TerminateProcess(self, pid, timeout):
        """Helper function to terminate a process, given the pid

        Args:
            pid: integer process id of the process to terminate.
        """
        ret = ''
        try:
            for sig in ('SIGABRT', 'SIGTERM', 'SIGKILL'):
                if utils.is_running(pid):
                    os.kill(pid, getattr(signal, sig))
                    time.sleep(timeout)
                    ret = 'killed with %s' % sig
        except OSError, (errno, strerror):
            print 'WARNING: failed os.kill: %s : %s' % (errno, strerror)
        return ret

