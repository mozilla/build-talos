#!/usr/bin/env python
#
# ***** BEGIN LICENSE BLOCK *****
# Version: MPL 1.1/GPL 2.0/LGPL 2.1
#
# The contents of this file are subject to the Mozilla Public License Version
# 1.1 (the "License"); you may not use this file except in compliance with
# the License. You may obtain a copy of the License at
# http://www.mozilla.org/MPL/
#
# Software distributed under the License is distributed on an "AS IS" basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License
# for the specific language governing rights and limitations under the
# License.
#
# The Original Code is standalone Firefox Windows performance test.
#
# The Initial Developer of the Original Code is Google Inc.
# Portions created by the Initial Developer are Copyright (C) 2006
# the Initial Developer. All Rights Reserved.
#
# Contributor(s):
#   Alice Nodelman <anodelman@mozilla.com> (original author)
#
# Alternatively, the contents of this file may be used under the terms of
# either the GNU General Public License Version 2 or later (the "GPL"), or
# the GNU Lesser General Public License Version 2.1 or later (the "LGPL"),
# in which case the provisions of the GPL or the LGPL are applicable instead
# of those above. If you wish to allow use of your version of this file only
# under the terms of either the GPL or the LGPL, and not to allow others to
# use your version of this file under the terms of the MPL, indicate your
# decision by deleting the provisions above and replace them with the notice
# and other provisions required by the GPL or the LGPL. If you do not delete
# the provisions above, a recipient may use your version of this file under
# the terms of any one of the MPL, the GPL or the LGPL.
#
# ***** END LICENSE BLOCK *****

__author__ = 'anodelman@mozilla.com (Alice Nodelman)'

import os
import time
import subprocess
import threading
import sys
import utils
import optparse

defaults = {'endTime': -1,
            'returncode': -1,
            'command': '',
            'browser_log': '',
            'url_mod': '',
            'test_timeout': 1200,
            'browser_wait': -1,
            'child_process': 'plugin-container',
            'process': 'firefox',
            'host':  '',
            'deviceroot': '',
            'port': 20701,
            'env': '', 'xperf_path': None,
            'xperf_providers': [], 'xperf_stackwalk': [],
            'configFile': 'bcontroller.yml'}

class BrowserWaiter(threading.Thread):
  def __init__(self, remoteProcess = None, **options):
      self.options = options
      self.remoteProcess = remoteProcess
      for key, value in defaults.items():
          setattr(self, key, options.get(key, value))

      threading.Thread.__init__(self)
      self.start()

  def run(self):
    if self.url_mod:
      if (self.remoteProcess): #working with a remote device
        if (self.url_mod == "str(int(time.time()*1000))"):
          curtime = self.remoteProcess.getCurrentTime()
          if curtime is None:
            self.returncode = 1
            self.endtime = 0
            return

          self.command += curtime
      else: #non-remote device
        self.command = self.command + eval(self.url_mod)

    self.firstTime = int(time.time()*1000)
    if (self.remoteProcess): #working with a remote device
      devroot = self.remoteProcess.getDeviceRoot()
      if (devroot == None):
        self.returncode = 1
      else:
        remoteLog = devroot + '/' + self.browser_log.split('/')[-1]
        retVal = self.remoteProcess.launchProcess(self.command, outputFile=remoteLog, timeout=self.test_timeout)
        if retVal <> None:
          self.remoteProcess.getFile(retVal, self.browser_log)
          self.returncode = 0
        else:
          data = self.remoteProcess.getFile(remoteLog, self.browser_log)
          if (data == ''):
            self.returncode = 1
          else:
            self.returncode = 0
    elif ((self.xperf_path is not None) and os.path.exists(self.xperf_path)):
      csvname = 'etl_output.csv'
      etlname = 'test.etl'

      #start_xperf.py -c <configfile> -e <etl filename>
      cmd = [sys.executable, os.path.join('xtalos', 'start_xperf.py'), '-c', self.configFile, '-e', etlname]
      try:
        subprocess.call(cmd)
      except:
        print "Error running '%s'." % subprocess.list2cmdline(cmd)
        self.returncode = 1

      self.returncode = os.system(self.command)

      #stop_xperf.py -x <path to xperf.exe>
      #etlparser.py -o <outputname[.csv]> -p <process_name (i.e. firefox.exe)> -c <path to configfile> -e <xperf_output[.etl]>
      cmd = [sys.executable, os.path.join('xtalos', 'stop_xperf.py'), '-x', self.xperf_path]
      try:
        subprocess.call(cmd)
      except:
        print "Error running '%s'." % subprocess.list2cmdline(cmd)
        self.returncode = 1

      cmd = [sys.executable,
             os.path.join('xtalos', 'etlparser.py'),
             '-o', csvname,
             '-p', self.process,
             '-e', etlname,
             '-c', self.configFile]
      try:
        subprocess.call(cmd)
      except:
        print "Error running '%s'." % subprocess.list2cmdline(cmd)
        self.returncode = 1

      print "__xperf_data_begin__"
      fhandle = open(csvname, 'r')
      print fhandle.read()
      fhandle.close()
      print "__xperf_data_end__"
    else:    #blocking call to system, non-remote device
      self.returncode = os.system(self.command + " > " + self.browser_log)

    self.endTime = int(time.time()*1000)

  def hasTime(self):
    return self.endTime > -1

  def getTime(self):
    return self.endTime

  def getFirstTime(self):
    return self.firstTime

  def getReturn(self):
    return self.returncode

class BrowserController:

  def __init__(self, options):
    self.remoteProcess = None
    options['env'] = ','.join(['%s=%s' % (str(key), str(value))
                               for key, value in options.get('env', {}).items()])

    if (options['xperf_path'] is not None and 
        (options['xperf_path'].strip() == 'None' or 
         options['xperf_path'].strip() == '')):
      options['xperf_path'] = None

    self.options = options
    for key, value in defaults.items():
        setattr(self, key, options.get(key, value)) 

    if (self.host):
      from ffprocess_remote import RemoteProcess
      self.remoteProcess = RemoteProcess(self.host, self.port, self.deviceroot)
      if self.env:
        self.command = ' "%s" %s' % (self.env, self.command)

  def run(self):
    self.bwaiter = BrowserWaiter(self.remoteProcess, **self.options)
    noise = 0
    prev_size = 0
    while not self.bwaiter.hasTime():
      if noise > self.test_timeout: # check for frozen browser
        if os.path.isfile(self.browser_log):
          os.chmod(self.browser_log, 0777)
        results_file = open(self.browser_log, "a")
        results_file.write("\n__FAILbrowser frozen__FAIL\n")
        results_file.close()
        return
      time.sleep(1)
      try:
        open(self.browser_log, "r").close() #HACK FOR WINDOWS: refresh the file information
        size = os.path.getsize(self.browser_log)
      except:
        size = 0

      if size > prev_size:
        prev_size = size
        noise = 0
      else:
        noise += 1

    results_file = open(self.browser_log, "a")
    if self.bwaiter.getReturn() != 0:  #the browser shutdown, but not cleanly
      results_file.write("\n__FAILbrowser non-zero return code (%d)__FAIL\n" % self.bwaiter.getReturn())
      results_file.close()
      return
    results_file.write("__startBeforeLaunchTimestamp%d__endBeforeLaunchTimestamp\n" % self.bwaiter.getFirstTime())
    results_file.write("__startAfterTerminationTimestamp%d__endAfterTerminationTimestamp\n" % self.bwaiter.getTime())
    results_file.close()
    return

class BControllerOptions(optparse.OptionParser):
    """Parses BController commandline options."""
    def __init__(self, **kwargs):
        optparse.OptionParser.__init__(self, **kwargs)
        defaults = {}

        self.add_option("-f", "--configFile",
                        action = "store", dest = "configFile",
                        help = "path to a yaml config file for bcontroller")
        defaults["configFile"] = ''

def main(argv=None):
    parser = BControllerOptions()
    options, args = parser.parse_args()

    if not options.configFile:
        print >> sys.stderr, "FAIL: bcontroller.py requires a --configFile parameter\n"
        return

    configFile = options.configFile
    options = utils.readConfigFile(options.configFile)
    options['configFile'] = configFile

    if (len(options.get('command', '')) < 3 or \
        options.get('browser_wait', -1) <= 0 or \
        len(options.get('browser_log', '')) < 3):
      print >> sys.stderr, "FAIL: incorrect parameters to bcontroller\n"
      return

    bcontroller = BrowserController(options)
    bcontroller.run()

if __name__ == "__main__":
    sys.exit(main())
