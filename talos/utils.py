# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Utility functions for Talos"""

import os
import shlex
import subprocess
import sys
import time
import urlparse
import yaml
import string
import mozlog
from mozlog import debug,info
import platform
from mozprocess import pid as mozpid

# directory of this file for use with interpolatePath()
here = os.path.dirname(os.path.realpath(__file__))

DEBUG = 0
NOISY = 0
START_TIME = 0
saved_environment = {}
log_levels = {'debug': mozlog.DEBUG, 'info': mozlog.INFO}

def startTimer():
    global START_TIME
    START_TIME = time.time()

def stopTimer():
    stop_time = time.time()
    return time.strftime("%H:%M:%S", time.gmtime(stop_time-START_TIME))

def startLogger(levelChoice):
    #declare and define global logger object to send logging messages to
    mozlog.basicConfig(format = '%(levelname)s : %(message)s', level = log_levels[levelChoice])

def stamped_msg(msg_title, msg_action):
    """Prints a message to the console with a time stamp
    """
    time_format = "%a, %d %b %Y %H:%M:%S"
    msg_format = "%s: \n\t\t%s %s"
    print msg_format % (msg_title, msg_action, time.strftime(time_format, time.localtime()))
    sys.stdout.flush()

def setEnvironmentVars(newVars):
    """Sets environment variables as specified by env, an array of variables
    from sample.config"""
    global saved_environment
    env = os.environ
    for var in newVars:
        # save the old values so they can be restored later:
        try:
            saved_environment[var] = str(env[var])
        except :
            saved_environment[var] = ""
        env[var] = str(newVars[var])

def restoreEnvironmentVars():
    """Restores environment variables to the state they were in before
    setEnvironmentVars() was last called"""
    for var in saved_environment:
        os.environ[var] = saved_environment[var]

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

def writeConfigFile(obj, vals):
    retVal = ""
    if (vals == []):
        vals = obj.keys()

    for opt in vals:
        retVal += "%s: %s\n" % (opt, obj[opt])

    return retVal

def readConfigFile(filename):
    config_file = open(filename, 'r')
    yaml_config = yaml.load(config_file)
    config_file.close()
    return yaml_config

def zip_extractall(zipfile, rootdir):
    #moved from ffsetup.py only required for python versions lower than 2.6
    """Python 2.4 compatibility instead of ZipFile.extractall."""
    for name in zipfile.namelist():
        if name.endswith('/'):
            if not os.path.exists(os.path.join(rootdir, name)):
                os.makedirs(os.path.join(rootdir, name))
        else:
            destfile = os.path.join(rootdir, name)
            destdir = os.path.dirname(destfile)
            if not os.path.isdir(destdir):
                os.makedirs(destdir)
            data = zipfile.read(name)
            f = open(destfile, 'wb')
            f.write(data)
            f.close()

def is_running(pid, psarg='axwww'):
    """returns if a pid is running"""
    return bool([i for i in mozpid.ps(psarg) if pid == int(i['PID'])])

def interpolatePath(path, profile_dir=None, firefox_path=None, robocop_TestPackage=None, robocop_TestName=None, webserver=None):
    path = string.Template(path).safe_substitute(talos=here)

    if robocop_TestName and robocop_TestPackage:
        path = string.Template(path).safe_substitute(robocopTestPackage=robocop_TestPackage)
        path = string.Template(path).safe_substitute(robocopTestName=robocop_TestName)

    if profile_dir:
        path = string.Template(path).safe_substitute(profile=profile_dir)

    if firefox_path:
        path = string.Template(path).safe_substitute(firefox=firefox_path)

    if webserver:
        scheme = ''
        if ('://' not in webserver):
            scheme = 'http://'
        path = string.Template(path).safe_substitute(webserver='%s%s' % (scheme, webserver))

    return path

def testAgent(host, port):
    from mozdevice import droid
    if port == -1:
        return droid.DroidADB(host, port, deviceRoot='/mnt/sdcard/tests')
    else:
        return droid.DroidSUT(host, port, deviceRoot='/mnt/sdcard/tests')

def findall(string, token):
    """find all occurances in a string"""
    # really, should be in python core
    retval = []
    while True:
        if retval:
            index = retval[-1] + len(token)
        else:
            index = 0
        location = string.find(token, index)
        if location == -1:
            return retval
        retval.append(location)

def tokenize(string, start, end):
    """
    tokenize a string by start + end tokens,
    returns parts and position of last token
    """
    assert end not in start, "End token '%s' is contained in start token '%s'" % (end, start)
    assert start not in end, "Start token '%s' is contained in end token '%s'" % (start, end)
    _start = findall(string, start)
    _end = findall(string, end)
    if not _start and not _end:
        return [], -1
    assert len(_start), "Could not find start token: '%s'" % start
    assert len(_end), "Could not find end token: '%s'" % end
    assert len(_start) == len(_end), "Unmatched number of tokens found: '%s' (%d) vs '%s' (%d)" % (start, len(_start), end, len(_end))
    for i in range(len(_start)):
        assert _end[i] > _start[i], "End token '%s' occurs before start token '%s'" % (end, start)
    parts = []
    for i in range(len(_start)):
        parts.append(string[_start[i] + len(start):_end[i]])
    return parts, _end[-1]

def MakeDirectoryContentsWritable(dirname):
    """Recursively makes all the contents of a directory writable.
       Uses os.chmod(filename, mod ), which works on Windows and Unix based systems.

    Args:
      dirname: Name of the directory to make contents writable.
    """
    os_name=os.name
    if os_name=='posix':
        mod=0755
    elif os_name=='nt':
        mod=0777
    else:
        print('WARNING : this action is not supported on your current os')
    try:
        for (root, dirs, files) in os.walk(dirname):
            os.chmod(root, mod)
            for filename in files:
                try:
                    os.chmod(os.path.join(root, filename), mod)
                except OSError, (errno, strerror):
                    print 'WARNING: failed to os.chmod(%s): %s : %s' % (os.path.join(root, filename), errno, strerror)
    except OSError, (errno, strerror):
        print 'WARNING: failed to MakeDirectoryContentsWritable: %s : %s' % (errno, strerror)

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

def parsePref(value):
    """parse a preference value from a string"""
    if not isinstance(value, basestring):
        return value
    if value.lower() == 'true':
        return True
    if value.lower() == 'false':
        return False
    try:
        return int(value)
    except ValueError:
        return value

def GenerateBrowserCommandLine(browser_path, extra_args, deviceroot, profile_dir, url):
    #TODO: allow for spaces in file names on Windows

    command_args = [browser_path.strip()]
    if platform.system() == "Darwin":
        command_args.extend(['-foreground'])

    #TODO: figure out a robust method to allow extra_args as a list instead of assuming a string
    if extra_args.strip():
        command_args.extend([extra_args])

    command_args.extend(['-profile', profile_dir])
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
