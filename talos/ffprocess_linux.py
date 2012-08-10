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

    def GenerateBrowserCommandLine(self, browser_path, extra_args, profile_dir, url):
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


    def GetPidsByName(self, process_name):
        """Searches for processes containing a given string.
            This function is UNIX specific.

        Args:
            process_name: The string to be searched for

        Returns:
            A list of PIDs containing the string. An empty list is returned if none are
            found.
        """
        processes = utils.running_processes(process_name)
        return [pid for pid,_ in processes]

    def TerminateProcess(self, pid, timeout):
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

    def TerminateAllProcesses(self, timeout, *process_names):
        """Helper function to terminate all processes with the given process name

        Args:
            process_names: String or strings containing the process name, i.e. "firefox"
        """

        # Get all the process ids of running instances of this process,
        # and terminate them
        result = ''
        for process_name in process_names:
            pids = self.GetPidsByName(process_name)
            for pid in pids:
                ret = self.TerminateProcess(pid, timeout)
                if result and ret:
                    result = result + ', '
                if ret:
                    result = result + process_name + '(' + str(pid) + '): ' + ret 
        return result


    def NonBlockingReadProcessOutput(self, handle):
        """Does a non-blocking read from the output of the process
            with the given handle.

        Args:
            handle: The process handle returned from os.popen()
            
        Returns:
            A tuple (bytes, output) containing the number of output
            bytes read, and the actual output.
        """

        output = ""
        num_avail = 0

        # check for data
        # select() does not seem to work well with pipes.
        # after data is available once it *always* thinks there is data available
        # readline() will continue to return an empty string however
        # so we can use this behavior to work around the problem
        while select([handle], [], [], 0)[0]:
            line = handle.readline()
            if line:
                output += line
            else:
                break
            # this statement is true for encodings that have 1byte/char
            num_avail = len(output)

        return (num_avail, output)
