# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import time
import logging
from mozprocess import ProcessHandler
from threading import Event

from utils import TalosError


class Reader(object):
    def __init__(self, event):
        self.output = []
        self.got_end_timestamp = False
        self.event = event

    def __call__(self, line):
        if line.find('__endTimestamp') != -1:
            self.got_end_timestamp = True
            self.event.set()

        if not (line.startswith('JavaScript error:') or
                line.startswith('JavaScript warning:')):
            print line
            self.output.append(line)


def run_browser(command, timeout=None, on_started=None, **kwargs):
    """
    Run the browser using the given `command`.

    After the browser prints __endTimestamp, we give it 5
    seconds to quit and kill it if it's still alive at that point.

    :param command: the commad (as a string list) to run the browser
    :param timeout: if specified, timeout to wait for the browser before
                    we raise a :class:`TalosError`
    :param on_started: a callback that can be used to do things just after
                       the browser has been started
    :param kwargs: additional keyword arguments for the :class:`ProcessHandler`
                   instance

    Returns a tuple (pid, output) where output is a list of strings.
    """
    first_time = int(time.time()) * 1000
    wait_for_quit_timeout = 5
    event = Event()
    reader = Reader(event)

    kwargs['storeOutput'] = False
    kwargs['processOutputLine'] = reader
    kwargs['onFinish'] = event.set
    proc = ProcessHandler(command, **kwargs)
    proc.run()
    try:
        if on_started:
            on_started()
        # wait until we saw __endTimestamp in the proc output,
        # or the browser just terminated - or we have a timeout
        if not event.wait(timeout):
            raise TalosError("timeout")
        if reader.got_end_timestamp:
            for i in range(1, wait_for_quit_timeout):
                if proc.wait(1) is not None:
                    break
            if proc.returncode is not None:
                logging.info(
                    "Browser shutdown timed out after {0} seconds, terminating"
                    " process.".format(wait_for_quit_timeout)
                )
    finally:
        # this also handle KeyboardInterrupt
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=1)  # wait a bit for complete termination

    reader.output.append(
        "__startBeforeLaunchTimestamp%d__endBeforeLaunchTimestamp"
        % first_time)
    reader.output.append(
        "__startAfterTerminationTimestamp%d__endAfterTerminationTimestamp"
        % (int(time.time()) * 1000))

    logging.info("Browser exited with error code: {0}".format(proc.returncode))
    return proc.pid, reader.output
