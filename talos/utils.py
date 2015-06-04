# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Utility functions for Talos"""

import os
import sys
import time
import urlparse
import string
import urllib
import mozinfo
import mozlog
import json
import re
from mozlog import debug, info  # this is silly, but necessary
import platform
import shutil
import copy
from contextlib import contextmanager

# directory of this file for use with interpolatePath()
here = os.path.dirname(os.path.realpath(__file__))


class Timer(object):
    def __init__(self):
        self._start_time = 0
        self.start()

    def start(self):
        self._start_time = time.time()

    def elapsed(self):
        seconds = time.time() - self._start_time
        return time.strftime("%H:%M:%S", time.gmtime(seconds))


def startLogger(levelChoice):
    # declare and define global logger object to send logging messages to
    log_levels = {'debug': mozlog.DEBUG, 'info': mozlog.INFO}
    mozlog.basicConfig(format='%(levelname)s : %(message)s',
                       level=log_levels[levelChoice])


def stamped_msg(msg_title, msg_action):
    """Prints a message to the console with a time stamp
    """
    time_format = "%a, %d %b %Y %H:%M:%S"
    msg_format = "%s: \n\t\t%s %s"
    print msg_format % (msg_title, msg_action,
                        time.strftime(time_format, time.localtime()))
    sys.stdout.flush()


@contextmanager
def restore_environment_vars():
    """
    clone the os.environ variable then restore it at the end.

    This is intended to be used like this: ::

      with restore_environment_vars():
          # os.environ is a copy
          os.environ['VAR'] = '1'
      # os.environ is restored
    """
    backup_env, os.environ = os.environ, copy.deepcopy(os.environ)
    try:
        yield
    finally:
        os.environ = backup_env


class TalosError(Exception):
    "Errors found while running the talos harness."


class TalosRegression(Exception):
    """When a regression is detected at runtime, report it properly
       Currently this is a simple definition so we can detect the class type
    """


class TalosCrash(Exception):
    """Exception type where we want to report a crash and stay
       compatible with tbpl while allowing us to continue on.

       https://bugzilla.mozilla.org/show_bug.cgi?id=829734
    """


def is_running(pid, psarg='axwww'):
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


def interpolate(template, **kwargs):
    """
    Use string.Template to substitute variables in a string.

    The placeholder ${talos} is always defined and will be replaced by the
    folder containing this file (global variable 'here').

    You can add placeholders using kwargs.
    """
    kwargs.setdefault('talos', here)
    return string.Template(template).safe_substitute(**kwargs)


def testAgent(host, port):
    from mozdevice import droid
    if port == -1:
        return droid.DroidADB(host, port, deviceRoot='/mnt/sdcard/tests')
    else:
        return droid.DroidSUT(host, port, deviceRoot='/mnt/sdcard/tests')


def findall(string, token):
    """find all occurences in a string"""
    return [m.start() for m in re.finditer(re.escape(token), string)]


def tokenize(string, start, end):
    """
    tokenize a string by start + end tokens,
    returns parts and position of last token
    """
    assert end not in start, \
        "End token '%s' is contained in start token '%s'" % (end, start)
    assert start not in end, \
        "Start token '%s' is contained in end token '%s'" % (start, end)
    _start = findall(string, start)
    _end = findall(string, end)
    if not _start and not _end:
        return [], -1
    assert len(_start), "Could not find start token: '%s'" % start
    assert len(_end), "Could not find end token: '%s'" % end
    assert len(_start) == len(_end), \
        ("Unmatched number of tokens found: '%s' (%d) vs '%s' (%d)"
         % (start, len(_start), end, len(_end)))
    for i in range(len(_start)):
        assert _end[i] > _start[i], \
            "End token '%s' occurs before start token '%s'" % (end, start)
    parts = []
    for i in range(len(_start)):
        parts.append(string[_start[i] + len(start):_end[i]])
    return parts, _end[-1]


def MakeDirectoryContentsWritable(dirname):
    """Recursively makes all the contents of a directory writable.
       Uses os.chmod(filename, mod ), which works on Windows and Unix
       based systems.

    Args:
      dirname: Name of the directory to make contents writable.
    """
    os_name = os.name
    if os_name == 'posix':
        mod = 0755
    elif os_name == 'nt':
        mod = 0777
    else:
        print('WARNING : this action is not supported on your current os')
    try:
        for (root, dirs, files) in os.walk(dirname):
            os.chmod(root, mod)
            for filename in files:
                try:
                    os.chmod(os.path.join(root, filename), mod)
                except OSError, (errno, strerror):
                    print ('WARNING: failed to os.chmod(%s): %s : %s'
                           % (os.path.join(root, filename), errno, strerror))
    except OSError, (errno, strerror):
        print ('WARNING: failed to MakeDirectoryContentsWritable: %s : %s'
               % (errno, strerror))


def urlsplit(url, default_scheme='file'):
    """front-end to urlparse.urlsplit"""

    if '://' not in url:
        url = '%s://%s' % (default_scheme, url)

    if url.startswith('file://'):
        # file:// URLs do not play nice with windows
        # https://bugzilla.mozilla.org/show_bug.cgi?id=793875
        return ['file', '', url[len('file://'):], '', '']

    # split the URL and return a list
    return [i for i in urlparse.urlsplit(url)]


def parse_pref(value):
    """parse a preference value from a string"""
    from mozprofile.prefs import Preferences
    return Preferences.cast(value)


def GenerateBrowserCommandLine(browser_path, extra_args, deviceroot,
                               profile_dir, url, profiling_info=None):
    # TODO: allow for spaces in file names on Windows

    command_args = [browser_path.strip()]
    if platform.system() == "Darwin":
        command_args.extend(['-foreground'])

    if isinstance(extra_args, list):
        command_args.extend(extra_args)

    elif extra_args.strip():
        command_args.extend([extra_args])

    command_args.extend(['-profile', profile_dir])

    if profiling_info:
        # For pageloader, buildCommandLine() puts the -tp* command line
        # options into the url argument.
        # It would be better to assemble all -tp arguments in one place,
        # but we don't have the profiling information in buildCommandLine().
        if url.find(' -tp') != -1:
            command_args.extend(['-tpprofilinginfo',
                                 json.dumps(profiling_info)])
        elif url.find('?') != -1:
            url += '&' + urllib.urlencode(profiling_info)
        else:
            url += '?' + urllib.urlencode(profiling_info)

    command_args.extend(url.split(' '))

    # Handle robocop case
    if url.startswith('am instrument'):
        command = url % deviceroot
        command_args = command.split(' ')

    # Handle media performance tests
    if url.find('media_manager.py') != -1:
        command_args = url.split(' ')

    debug("command line: %s", ' '.join(command_args))
    return command_args


def indexed_items(itr):
    """
    Generator that allows us to figure out which item is the last one so
    that we can serialize this data properly
    """
    prev_i, prev_val = 0, itr.next()
    for i, val in enumerate(itr, start=1):
        yield prev_i, prev_val
        prev_i, prev_val = i, val
    yield -1, prev_val


def rmtree_until_timeout(path, timeout):
    """
    Like shutils.rmtree, but retries until timeout seconds have elapsed.
    """
    elapsed = 0
    while True:
        try:
            shutil.rmtree(path)
            if elapsed > 0:
                info("shutil.rmtree({0}) succeeded after retrying for {1}"
                     " seconds.".format(path, elapsed))
            return
        except Exception as e:
            if elapsed >= timeout:
                info("shutil.rmtree({0}) still failing after retrying for"
                     " {1} seconds.".format(path, elapsed))
                raise e
            # Wait 1 second and retry.
            time.sleep(1)  # 1 second
            elapsed += 1
