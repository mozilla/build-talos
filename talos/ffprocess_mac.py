# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import subprocess
#HACK - http://www.gossamer-threads.com/lists/python/bugs/593800
#To stop non-threadsafe popen nonsense, should be removed when we upgrade to
#python 2.5 or later
subprocess._cleanup = lambda: None
import signal
import os
import time
from select import select
from ffprocess import FFProcess
import shutil
import utils
import platform


class MacProcess(FFProcess):

    def GenerateBrowserCommandLine(self, browser_path, extra_args, deviceroot, profile_dir, url):
        """Generates the command line for a process to run Browser

        Args:
            browser_path: String containing the path to the browser binary to use
            profile_dir: String containing the directory of the profile to run Browser in
            url: String containing url to start with.
        """

        profile_arg = ''
        if profile_dir:
            profile_arg = '-profile %s' % profile_dir

        cmd = '%s -foreground %s %s %s' % (browser_path,
                            extra_args,
                            profile_arg,
                            url)
        """
        If running on OS X 10.5 or older, wrap |cmd| so that it will
        be executed as an i386 binary, in case it's a 32-bit/64-bit universal
        binary.
        """
        if hasattr(platform, 'mac_ver') and platform.mac_ver()[0][:4] == '10.5':
            return "arch -arch i386 " + cmd

        return cmd

    def _GetPidsByName(self, process_name):
        """Searches for processes containing a given string.

        Args:
            process_name: The string to be searched for

        Returns:
            A list of PIDs containing the string. An empty list is returned if none are
            found.
        """
        processes = utils.running_processes(process_name, psarg='-Acj')
        return [pid for pid,_ in processes]

    def _TerminateProcess(self, pid, timeout):
        """Helper function to terminate a process, given the pid

        Args:
            pid: integer process id of the process to terminate.
        """
        ret = ''
        try:
            for sig in ('SIGTERM', 'SIGKILL'):
                if utils.is_running(pid, psarg='-Acj'):
                    os.kill(pid, getattr(signal, sig))
                    time.sleep(timeout)
                    ret = 'killed with %s' % sig
        except OSError, (errno, strerror):
            print 'WARNING: failed os.kill: %s : %s' % (errno, strerror)
        return ret

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
