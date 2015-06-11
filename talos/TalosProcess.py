# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

from mozprocess import ProcessHandler
from threading import Thread
import os
import time
import mozlog

from utils import TalosError


class TalosProcess(ProcessHandler):
    """
    Process handler for running peptests

    After the browser prints __endTimestamp, we give it wait_for_quit_timeout
    seconds to quit and kill it if it's still alive at that point.
    """
    def __init__(self, cmd, args=None, cwd=None,
                 env=None,
                 ignore_children=False,
                 logfile=None,
                 suppress_javascript_errors=False,
                 wait_for_quit_timeout=5,
                 **kwargs):

        self.firstTime = int(time.time()) * 1000
        self.logfile = logfile
        self.results_file = None
        self.suppress_javascript_errors = suppress_javascript_errors
        self.wait_for_quit_timeout = wait_for_quit_timeout
        if env is None:
            env = os.environ.copy()

        ProcessHandler.__init__(self, cmd, args=args, cwd=cwd, env=env,
                                ignore_children=ignore_children,
                                processOutputLine=self.processOutputLine,
                                **kwargs)

    def logToFile(self, msg):
        if not self.logfile:
            return

        if not self.results_file:
            self.results_file = open(self.logfile, 'w')

        self.results_file.write(msg)

    def closeLogFile(self):
        if self.results_file:
            self.results_file.close()

    def waitForQuit(self):
        for i in range(1, self.wait_for_quit_timeout):
            if self.proc.returncode is not None:
                self.logToFile(
                    "__startBeforeLaunchTimestamp%d"
                    "__endBeforeLaunchTimestamp\n"
                    % self.firstTime
                )
                self.logToFile(
                    "__startAfterTerminationTimestamp%d"
                    "__endAfterTerminationTimestamp\n"
                    % (int(time.time()) * 1000)
                )
                self.closeLogFile()
                return
            time.sleep(1)

        mozlog.info(
            "Browser shutdown timed out after {0} seconds, terminating"
            " process.".format(self.wait_for_quit_timeout)
        )
        self.proc.kill()
        self.logToFile(
            "__startBeforeLaunchTimestamp%d__endBeforeLaunchTimestamp\n"
            % self.firstTime
        )
        self.logToFile(
            "__startAfterTerminationTimestamp%d__endAfterTerminationTimestamp"
            "\n"
            % (int(time.time()) * 1000)
        )
        self.closeLogFile()

    def onTimeout(self):
        """
        When we timeout, dictate this in the log file.
        """
        if os.path.isfile(self.logfile):
            os.chmod(self.logfile, 0777)
        self.logToFile("\n__FAILbrowser frozen__FAIL\n")
        self.closeLogFile()
        raise TalosError("timeout")

    def processOutputLine(self, line):
        """
        Callback called on each line of output
        Search for signs of error
        """
        if line.find('__endTimestamp') != -1:
            thread = Thread(target=self.waitForQuit)
            thread.setDaemon(True)  # don't hang on quit
            thread.start()

        if self.suppress_javascript_errors and \
                (line.startswith('JavaScript error:') or
                 line.startswith('JavaScript warning:')):
            return

        print line
        self.logToFile(line + "\n")
