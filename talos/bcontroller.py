#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""talos browser controller"""

import os
import time
import subprocess
import threading
import sys
import utils
import optparse

from utils import talosError

defaults = {'endTime': -1,
            'returncode': -1,
            'command': '',
            'browser_log': '',
            'url_timestamp': False,
            'test_timeout': 1200,
            'browser_wait': -1,
            'child_process': 'plugin-container',
            'process': 'firefox',
            'host':  '',
            'deviceroot': '',
            'port': 20701,
            'env': '',
            'xperf_path': None,
            'xperf_providers': [],
            'xperf_user_providers': [],
            'xperf_stackwalk': [],
            'configFile': 'bcontroller.yml'}

class BrowserWaiter(threading.Thread):

  def __init__(self, remoteProcess=None, **options):
      self.options = options
      self.remoteProcess = remoteProcess
      for key, value in defaults.items():
          setattr(self, key, options.get(key, value))

      threading.Thread.__init__(self)
      self.start()

  def run(self):
    if self.url_timestamp:
      if self.remoteProcess: #working with a remote device
          curtime = self.remoteProcess.getCurrentTime()
          if curtime is None:
            self.returncode = 1
            self.endtime = 0
            return
      else: #non-remote device
        curtime = str(int(time.time()*1000))
      self.command += curtime

    self.firstTime = int(time.time()*1000)
    if self.remoteProcess: #working with a remote device
      devroot = self.remoteProcess.getDeviceRoot()
      if devroot is None:
        self.returncode = 1
      else:
        remoteLog = devroot + '/' + self.browser_log.split('/')[-1]
        retVal = self.remoteProcess.launchProcess(self.command, outputFile=remoteLog, timeout=self.test_timeout)
        if retVal <> None:
          self.remoteProcess.getFile(retVal, self.browser_log)
          self.returncode = 0
        else:
          data = self.remoteProcess.getFile(remoteLog, self.browser_log)
          if data == '':
            self.returncode = 1
          else:
            self.returncode = 0
    elif self.xperf_path and os.path.exists(self.xperf_path) and \
         self.xperf_stackwalk and \
         self.xperf_providers:
      csvname = 'etl_output.csv'
      etlname = 'test.etl'

      import xtalos

      # start xperf
      try:
        xtalos.start_from_config(self.configFile, etl_filename=etlname)
      except Exception, e:
        print "Error starting xperf: %s" % e
        self.returncode = 1

      # start firefox
      proc = subprocess.Popen(self.command)
      proc.wait()
      self.returncode = proc.returncode

      # stop xperf
      try:
        xtalos.stop(self.xperf_path)
      except Exception, e:
        print "Error stopping xperf: %s" % e
        self.returncode = 1

      # run the etl parser
      try:
          xtalos.etlparser.etlparser_from_config(self.configFile,
                                                 etl_filename=etlname,
                                                 outputFile=csvname,
                                                 processID=str(proc.pid)
                                                 )
      except Exception, e:
        print "Error running etlparser: %s" % e
        self.returncode = 1

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

class BrowserController(object):

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
        try:
          if os.path.isfile(self.browser_log):
            os.chmod(self.browser_log, 0777)
          results_file = open(self.browser_log, "a")
          results_file.write("\n__FAILbrowser frozen__FAIL\n")
          results_file.close()
        except IOError, e:
          raise talosError(str(e))
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
