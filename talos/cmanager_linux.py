# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import subprocess
import sys
import os

def GetPrivateBytes(pids):
  """Calculate the amount of private, writeable memory allocated to a process.
     This code was adapted from 'pmap.c', part of the procps project.
  """
  privateBytes = 0
  for pid in pids:
    mapfile = '/proc/%s/maps' % pid
    maps = open(mapfile)

    private = 0

    for line in maps:
      # split up
      (range,line) = line.split(" ", 1)

      (start,end) = range.split("-")
      flags = line.split(" ", 1)[0]

      size = int(end, 16) - int(start, 16)

      if flags.find("p") >= 0:
        if flags.find("w") >= 0:
          private += size

    privateBytes += private
    maps.close()

  return privateBytes


def GetResidentSize(pids):
  """Retrieve the current resident memory for a given process"""
  # for some reason /proc/PID/stat doesn't give accurate information
  # so we use status instead

  RSS = 0
  for pid in pids:
    file = '/proc/%s/status' % pid

    status = open(file)

    for line in status:
      if line.find("VmRSS") >= 0:
        RSS += int(line.split()[1]) * 1024

    status.close()

  return RSS

def GetXRes(pids):
  """Returns the total bytes used by X or raises an error if total bytes is not available"""
  XRes = 0
  for pid in pids:
    cmdline = "xrestop -m 1 -b | grep -A 15 " + str(pid) + " | tr -d \"\n\" | sed \"s/.*total bytes.*: ~//g\""
    try:
      pipe = subprocess.Popen(cmdline, shell=True, stdout=-1).stdout
      data = pipe.read()
      pipe.close()
    except:
      print "Unexpected error executing '%s': %s", (cmdline, sys.exc_info())
      raise
    try:
      data = float(data)
      XRes += data
    except:
      print "Invalid data, not a float"
      raise

  return XRes

counterDict = {}
counterDict["Private Bytes"] = GetPrivateBytes
counterDict["RSS"] = GetResidentSize
counterDict["XRes"] = GetXRes

class CounterManager(object):
  """This class manages the monitoring of a process with any number of
     counters.

     A counter can be any function that takes an argument of one pid and
     returns a piece of data about that process.
     Some examples are: CalcCPUTime, GetResidentSize, and GetPrivateBytes
  """

  pollInterval = .25

  def __init__(self, ffprocess, process, counters=None, childProcess="plugin-container"):
    """Args:
         counters: A list of counters to monitor. Any counters whose name does
         not match a key in 'counterDict' will be ignored.
    """
    self.allCounters = {}
    self.registeredCounters = {}
    self.childProcess = childProcess
    self.runThread = False
    self.pidList = []
    self.ffprocess = ffprocess
    self.primaryPid = self.ffprocess.GetPidsByName(process)[-1]
    os.stat('/proc/%s' % self.primaryPid)

    self._loadCounters()
    self.registerCounters(counters)

  def _loadCounters(self):
    """Loads all of the counters defined in the counterDict"""
    for counter in counterDict.keys():
      self.allCounters[counter] = counterDict[counter]

  def registerCounters(self, counters):
    """Registers a list of counters that will be monitoring.
       Only counters whose names are found in allCounters will be added
    """
    for counter in counters:
      if counter in self.allCounters:
        self.registeredCounters[counter] = [self.allCounters[counter], []]

  def unregisterCounters(self, counters):
    """Unregister a list of counters.
       Only counters whose names are found in registeredCounters will be
       paid attention to
    """
    for counter in counters:
      if counter in self.registeredCounters:
        del self.registeredCounters[counter]

  def getCounterValue(self, counterName):
    """Returns the last value of the counter 'counterName'"""
    try:
      self.updatePidList()
      return self.registeredCounters[counterName][0](self.pidList)
    except:
      return None

  def updatePidList(self):
    """Updates the list of PIDs we're interested in"""
    try:
      self.pidList = [self.primaryPid]
      childPids = self.ffprocess.GetPidsByName(self.childProcess)
      for pid in childPids:
        os.stat('/proc/%s' % pid)
        self.pidList.append(pid)
    except:
      print "WARNING: problem updating child PID's"

  def stopMonitor(self):
    """any final cleanup"""
    # TODO: should probably wait until we know run() is completely stopped
    # before setting self.pid to None. Use a lock?
    return
