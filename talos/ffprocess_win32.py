# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from ffprocess import FFProcess
import os
import shutil
import utils
try:
    import mozprocess.wpk as wpk
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


    def _GetPidsByName(self, process_name):
        """Searches for processes containing a given string.

        Args:
            process_name: The string to be searched for
        
        Returns:
           A list of PIDs containing the string. An empty list is returned if none are
           found.
        """
        return wpk.get_pids(process_name)
 
    def _TerminateProcess(self, pid, timeout):
        wpk.kill_pid(pid)
        return "terminated with PROCESS_TERMINATE"

