# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import signal
import os
import time
from ffprocess import FFProcess
import utils


class MacProcess(FFProcess):

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
