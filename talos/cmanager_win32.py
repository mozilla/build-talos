# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import win32pdh
from cmanager import CounterManager

class WinCounterManager(CounterManager):

  def __init__(self, ffprocess, process, counters=None, childProcess="plugin-container"):
    self.ffprocess = ffprocess
    self.childProcess = childProcess
    self.registeredCounters = {}
    self.registerCounters(counters)
    # PDH might need to be "refreshed" if it has been queried while the browser
    # is closed
    win32pdh.EnumObjects(None, None, 0, 1)

    # Add the counter path for the default process.
    for counter in self.registeredCounters:
      path = win32pdh.MakeCounterPath((None, 'process', process,
                                       None, -1, counter))
      hq = win32pdh.OpenQuery()
      hc = None
      try:
        hc = win32pdh.AddCounter(hq, path)
      except:
        win32pdh.CloseQuery(hq)
        #assume that this is a memory counter for the system, not a process counter
        path = win32pdh.MakeCounterPath((None, 'Memory', None, None, -1 , counter))
        hq = win32pdh.OpenQuery()
        try:
          hc = win32pdh.AddCounter(hq, path)
        except:
          win32pdh.CloseQuery(hq)

      if hc:
        self.registeredCounters[counter] = [hq, [(hc, path)]]
        self.updateCounterPathsForChildProcesses(counter)


  def registerCounters(self, counters):
    # self.registeredCounters[counter][0] is a counter query handle
    # self.registeredCounters[counter][1] is a list of tuples, the first
    # member of which is a counter handle, the second a counter path
    for counter in counters:
      self.registeredCounters[counter] = []

  def updateCounterPathsForChildProcesses(self, counter):
    # Create a counter path for each instance of the child process that
    # is running.  If any of these paths are not in our counter list,
    # add them to our counter query and append them to the counter list,
    # so that we'll begin tracking their statistics.  We don't need to
    # worry about removing invalid paths from the list, as getCounterValue()
    # will generate a value of 0 for those.
    hq = self.registeredCounters[counter][0]
    win32pdh.EnumObjects(None, None, 0, 1)
    counterListLength = len(self.registeredCounters[counter][1])
    try:
      expandedCounterPaths = \
        win32pdh.ExpandCounterPath('\\process(%s*)\\%s' % (self.childProcess, counter))
    except:
      return
    for expandedPath in expandedCounterPaths:
      alreadyInCounterList = False
      for singleCounter in self.registeredCounters[counter][1]:
        if expandedPath == singleCounter[1]:
          alreadyInCounterList = True
      if not alreadyInCounterList:
        try:
          counterHandle = win32pdh.AddCounter(hq, expandedPath)
          self.registeredCounters[counter][1].append((counterHandle, expandedPath))
        except:
          continue
    if counterListLength != len(self.registeredCounters[counter][1]):
      try:
        win32pdh.CollectQueryData(hq)
      except:
        return

  def getCounterValue(self, counter):
    # Update counter paths, to catch any new child processes that might
    # have been launched since last call.  Then iterate through all
    # counter paths for this counter, and return a combined value.
    aggregateValue = 0
    if counter not in self.registeredCounters:
      return None

    if self.registeredCounters[counter] == []:
      return None

    self.updateCounterPathsForChildProcesses(counter)
    hq = self.registeredCounters[counter][0]

    # This call can throw an exception in the case where all counter paths
    # are invalid (i.e., all the processes have terminated).
    try:
      win32pdh.CollectQueryData(hq)
    except:
      return None

    for singleCounter in self.registeredCounters[counter][1]:
      hc = singleCounter[0]
      try:
        type, val = win32pdh.GetFormattedCounterValue(hc, win32pdh.PDH_FMT_LONG)
      except:
        val = 0
      aggregateValue += val

    return aggregateValue

  def getProcess(self):
    return self.process

  def stopMonitor(self):
    try:
      for counter in self.registeredCounters:
        for singleCounter in self.registeredCounters[counter][1]:
          win32pdh.RemoveCounter(singleCounter[0])
        win32pdh.CloseQuery(self.registeredCounters[counter][0])
      self.registeredCounters.clear()
    except:
      print 'failed to stopMonitor'
