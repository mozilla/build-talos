# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from ffprocess import FFProcess
import os
import shutil
import utils

try:
    import win32api
    import win32file
    import win32pdhutil
    import win32pdh
    import win32pipe
    import msvcrt
except:
    pass

class Win32Process(FFProcess):

    _directory_write_mode = 0777
    extra_prog=FFProcess.extra_prog[:] + ['dwwim']
    def GenerateBrowserCommandLine(self, browser_path, extra_args, deviceroot, profile_dir, url):
        """Generates the command line for a process to run Browser

        Args:
            browser_path: String containing the path to the browser exe to use
            profile_dir: String containing the directory of the profile to run Browser in
            url: String containing url to start with.
        """

        profile_arg = ''
        if profile_dir:
            profile_dir = profile_dir.replace('\\', '\\\\\\')
            profile_arg = '-profile %s' % profile_dir

        #Escaped quotes around cmd & double quotes around browser_path to allow paths containing spaces
        cmd = '\'"%s" %s %s %s\'' % (browser_path,
                                     extra_args,
                                     profile_arg,
                                     url)
        return cmd


    def TerminateProcess(self, pid):
        """Helper function to terminate a process, given the pid

        Args:
            pid: integer process id of the process to terminate.
        """
        ret = ''
        PROCESS_TERMINATE = 1
        handle = win32api.OpenProcess(PROCESS_TERMINATE, False, pid)
        win32api.TerminateProcess(handle, -1)
        win32api.CloseHandle(handle)
        ret = 'terminated with PROCESS_TERMINATE'
        return ret


    def ProcessesWithNames(self, *process_names):
        """Returns a list of processes running with the given name(s).
        Useful to check whether a Browser process is still running

        Args:
            process_names: String or strings containing process names, i.e. "firefox"

        Returns:
            An array with a list of processes in the list which are running
        """

        processes_with_names = []
        for process_name in process_names:
            try:
                # refresh list of processes
                win32pdh.EnumObjects(None, None, 0, 1)
                pids = win32pdhutil.FindPerformanceAttributesByName(process_name, counter="ID Process")
                if len(pids) > 0:
                    processes_with_names.extend([(pid, process_name) for pid in pids])
            except:
                # Might get an exception if there are no instances of the process running.
                continue
        return processes_with_names

    def TerminateAllProcesses(self, *process_names):
        """Helper function to terminate all processes with the given process name

        Args:
            process_name: String or strings containing the process name, i.e. "firefox"
        """
        result = ''
        for process_name in process_names:
            # Get all the process ids of running instances of this process, and terminate them.
            try:
                # refresh list of processes
                win32pdh.EnumObjects(None, None, 0, 1)
                pids = win32pdhutil.FindPerformanceAttributesByName(process_name, counter="ID Process")
                for pid in pids:
                    ret = self.TerminateProcess(pid)
                    if result and ret:
                        result = result + ', '
                    if ret:
                        result = result + process_name + '(' + str(pid) + '): ' + ret
            except:
                # Might get an exception if there are no instances of the process running.
                continue
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

        try:
            osfhandle = msvcrt.get_osfhandle(handle.fileno())
            (read, num_avail, num_message) = win32pipe.PeekNamedPipe(osfhandle, 0)
            if num_avail > 0:
                (error_code, output) = win32file.ReadFile(osfhandle, num_avail, None)

            return (num_avail, output)
        except:
            return (0, output)
