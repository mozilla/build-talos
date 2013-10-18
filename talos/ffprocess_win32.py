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

    def _TerminateProcess(self, pid, timeout):
        wpk.kill_pid(pid)
        return "terminated with PROCESS_TERMINATE"

