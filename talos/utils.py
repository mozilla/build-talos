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

# directory of this file for use with interpolatePath()
here = os.path.dirname(os.path.realpath(__file__))

DEBUG = 0
NOISY = 0
START_TIME = 0
saved_environment = {}

def startTimer():
  global START_TIME
  START_TIME = time.time()

def stopTimer():
  stop_time = time.time()
  return time.strftime("%H:%M:%S", time.gmtime(stop_time-START_TIME))

def setdebug(val):
  global DEBUG
  DEBUG = val

def setnoisy(val):
  global NOISY
  NOISY = val

def noisy(message):
  """Prints messages from the browser/application that are generated, otherwise
     these are ignored.  Controlled through command line switch (-n or --noisy)
  """
  if NOISY == 1:
    lines = message.splitlines()
    counter = 1
    for line in lines:
      print "NOISE: " + line
      #really silly throttling
      if counter % 100 == 0:
        time.sleep(1) #twisted.spread.banana.BananaError: string is too long to send (803255)
      sys.stdout.flush()
      counter += 1

def debug(message):
  """Prints a debug message to the console if the DEBUG switch is turned on 
     debug switch is controlled through command line switch (-d or --debug)
     Args:
       message: string containing a debugging statement
  """
  if DEBUG == 1:
    lines = message.splitlines()
    counter = 1
    for line in lines:
      print "DEBUG: " + line
      #really silly throttling
      if counter % 100 == 0:
        time.sleep(1) #twisted.spread.banana.BananaError: string is too long to send (803255)
      sys.stdout.flush()
      counter += 1

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

class talosError(Exception):
  def __init__(self, msg):
    self.msg = msg
  def __str__(self):
    return repr(self.msg)

class talosCrash(Exception):
  """Exception type where we want to report a crash and stay
     compatible with tbpl while allowing us to continue on.

     https://bugzilla.mozilla.org/show_bug.cgi?id=829734
  """
  def __init__(self, msg):
    self.msg = msg
  def __str__(self):
    return repr(self.msg)

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

def _parse_ps(_ps_output):
  """parse the output of the ps command"""
  retval = []
  header = None
  for line in _ps_output.splitlines():
    line = line.strip()
    if header is None:
      # first line is the header
      header = line.split()
      continue
    split = line.split(None, len(header)-1)
    if len(split) < len(header):
      if 'STAT' in header and len(split) == len(header) - 1:
        # STAT may be empty on ps -Acj for Mac
        # https://bugzilla.mozilla.org/show_bug.cgi?id=734146
        stat_index = header.index('STAT')
        split.insert(stat_index, '')
      else:
        print >> sys.stderr, "ps %s output:" % arg
        print >> sys.stderr, _ps_output
        raise talosError("ps line, '%s', does not match headers: %s" % (line, header))
    process_dict = dict(zip(header, split))
    retval.append(process_dict)
  return retval

def ps(arg='axwww'):
  """
  python front-end to `ps`
  http://en.wikipedia.org/wiki/Ps_%28Unix%29
  """
  global _ps_output # last ps output, for diagnostics
  process = subprocess.Popen(['ps', arg], stdout=subprocess.PIPE)
  _ps_output, _ = process.communicate()
  return _parse_ps(_ps_output)

def is_running(pid, psarg='axwww'):
  """returns if a pid is running"""
  return bool([i for i in ps(psarg) if pid == int(i['PID'])])

def running_processes(name, psarg='axwww', defunct=False):
  """
  returns a list of 2-tuples of running processes:
  (pid, ['path/to/executable', 'args', '...'])
  with the executable named `name`.
  - defunct: whether to return defunct processes
  """
  retval = []
  for process in ps(psarg):
    command = process.get('COMMAND', process.get('CMD'))
    if command is None:
      print >> sys.stderr, "ps %s output:" % psarg
      print >> sys.stderr, _ps_output
      raise talosError("command not found in %s" % process)

    if name not in command:
      # filter out commands where the name doesn't occur
      continue

    try:
      command = shlex.split(command)
    except ValueError:
      # https://bugzilla.mozilla.org/show_bug.cgi?id=784863
      # shlex error in checking for processes in utils.py
      print command
      raise

    if command[-1] == '<defunct>':
      # ignore defunct processes
      command = command[:-1]
      if not command or not defunct:
        continue

    if 'STAT' in process and not defunct:
      if process['STAT'] == 'Z+':
        # ignore zombie processes
        continue

    prog = command[0]
    if prog.startswith('(') and prog.endswith(')'):
      prog = prog[1:-1]
    basename = os.path.basename(prog)
    if basename == name:
      retval.append((int(process['PID']), command))
  return retval

def interpolatePath(path):
  return string.Template(path).safe_substitute(talos=here)

def testAgent(host, port):
  if port == -1:
    from mozdevice import devicemanagerADB
    return devicemanagerADB.DeviceManagerADB(host, port)
  else:
    from mozdevice import devicemanagerSUT
    return devicemanagerSUT.DeviceManagerSUT(host, port)

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

# methods for introspecting network availability
# Used for the --develop option where we dynamically create a webserver

def findOpenPort(ip):
  # XXX we don't import this at the top of the file
  # as this requires hashlib and talos on windows
  # is still on python 2.4 and "we don't care" if
  # devicemanager requires a higher version
  from mozdevice import devicemanager
  nettools = devicemanager.NetworkTools()
  return nettools.findOpenPort(ip, 15707)

def getLanIp():
  # XXX we don't import this at the top of the file
  # as this requires hashlib and talos on windows
  # is still on python 2.4 and "we don't care" if
  # devicemanager requires a higher version
  from mozdevice import devicemanager
  nettools = devicemanager.NetworkTools()
  ip = nettools.getLanIp()
  port = findOpenPort(ip)
  return "%s:%s" % (ip, port)

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
