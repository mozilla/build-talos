# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Firefox process management for Talos"""

import os
import signal
import time
import mozlog
import mozinfo
from utils import TalosError


def is_running(pid):
    """returns if a pid is running"""
    if mozinfo.isWin:
        from ctypes import sizeof, windll, addressof
        from ctypes.wintypes import DWORD

        BIG_ARRAY = DWORD * 4096
        processes = BIG_ARRAY()
        needed = DWORD()

        pids = []
        result = windll.psapi.EnumProcesses(processes,
                                            sizeof(processes),
                                            addressof(needed))
        if result:
            num_results = needed.value / sizeof(DWORD)
            for i in range(num_results):
                pids.append(int(processes[i]))
    else:
        from mozprocess import pid as mozpid
        pids = [int(i['PID']) for i in mozpid.ps()]

    return bool([i for i in pids if pid == i])


def running_processes(pids):
    """filter pids and return only the running ones"""
    return [pid for pid in pids if is_running(pid)]


if mozinfo.os == 'win':
    def terminate_process(pid, timeout):
        from mozprocess import wpk
        wpk.kill_pid(pid)
else:
    if mozinfo.os == 'linux':
        DEFAULT_SIGNALS = ('SIGABRT', 'SIGTERM', 'SIGKILL')
    else:
        DEFAULT_SIGNALS = ('SIGTERM', 'SIGKILL')

    def terminate_process(pid, timeout):
        ret = ''
        try:
            for sig in DEFAULT_SIGNALS:
                if is_running(pid):
                    os.kill(pid, getattr(signal, sig))
                    time.sleep(timeout)
                    ret = 'killed with %s' % sig
        except OSError, (errno, strerror):
            print 'WARNING: failed os.kill: %s : %s' % (errno, strerror)
        return ret


def terminate_processes(pids, timeout):
    results = []
    for pid in pids[:]:
        ret = terminate_process(pid, timeout)
        if ret:
            results.append("(%s): %s" % (pid, ret))
        else:
            # Remove PIDs which are already terminated
            # TODO: we will never be here on windows!
            pids.remove(pid)
    return ",".join(results)


def cleanup_processes(pids, timeout):
    # kill any remaining browser processes
    # returns string of which process_names were terminated and with
    # what signal

    mozlog.debug("Terminating: %s", ", ".join(str(pid) for pid in pids))
    terminate_result = terminate_processes(pids, timeout)
    # check if anything is left behind
    if running_processes(pids):
        # this is for windows machines.  when attempting to send kill
        # messages to win processes the OS
        # always gives the process a chance to close cleanly before
        # terminating it, this takes longer
        # and we need to give it a little extra time to complete
        time.sleep(timeout)
        process_pids = running_processes(pids)
        if process_pids:
            raise TalosError(
                "failed to cleanup process with PID: %s" % process_pids)

    return terminate_result
