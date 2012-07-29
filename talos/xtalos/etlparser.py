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
# The Original Code is mozilla.org code.
#
# The Initial Developer of the Original Code is
# the Mozilla Foundation.
# Portions created by the Initial Developer are Copyright (C) 2011
# the Initial Developer. All Rights Reserved.
#
# Contributor(s):
#   Joel Maher <joel.maher@gmail.com>
#   Nicolas Chaim <nicolas@n1.cl>
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

import csv
import re
import os
import optparse
import sys
import xtalos
import subprocess

#required for the autolog stuff
import yaml
import time
from mozautolog import RESTfulAutologTestGroup

EVENTNAME_INDEX = 0
PROCESS_INDEX = 2
THREAD_ID_INDEX = 3
DISKBYTES_COL = "Size"
FNAME_COL = "FileName"
IMAGEFUNC_COL = "Image!Function"
EVENTGUID_COL = "EventGuid"
ACTIVITY_ID_COL = "etw:ActivityId"
NUMBYTES_COL = "NumBytes"

CEVT_WINDOWS_RESTORED = "{917b96b1-ecad-4dab-a760-8d49027748ae}"
CEVT_XPCOM_SHUTDOWN   = "{26d1e091-0ae7-4f49-a554-4214445c505c}"
stages = ["startup", "normal", "shutdown"]
net_events = {"TcpDataTransferReceive": "recv", "UdpEndpointReceiveMessages": "recv",
              "TcpDataTransferSend": "send", "UdpEndpointSendMessages": "send"}
gThreads = {}
gConnectionIDs = {}
gHeaders = {}

def addHeader(eventType, data):
  gHeaders[eventType] = data

class XPerfAutoLog(object):

  def __init__(self, filename = None):
    self.testGroup = None
    if filename != None:
      config_file = open(filename, 'r')
      self.yaml_config = yaml.load(config_file)
      config_file.close()
      self.autolog_init()

  def autolog_init(self):
    testos = 'win7' #currently we only run xperf on windows 7
    testname = self.yaml_config.get('testname', '')
    testplatform = 'win32' #currently we only run xperf on win32
    if testname == '':
      return
  
    self.testGroup = RESTfulAutologTestGroup(
      testgroup = testname,
      os = testos,
      platform = testplatform,
      machine = self.yaml_config['title'],
      starttime = int(time.time()),
      builder = '%s_%s-opt_test-%s' % (self.yaml_config['title'], os, testname),
      restserver = 'http://10.2.74.141/autologserver'
    )
  
    tree = self.yaml_config.get('repository', '')
    if tree:
      tree = tree.split('/')[-1]
    self.testGroup.set_primary_product(
      tree = tree,
      buildtype = 'opt', #we only run talos on opt builds
      buildid = self.yaml_config['buildid'],
      revision = self.yaml_config['sourcestamp'],
    )

  def addData(self, filename, readcount, readbytes, writecount, writebytes):
    if (self.testGroup == None):
      self.autolog_init()

    if (self.testGroup == None):
      return
      
    self.testGroup.add_perf_data(
      test = self.yaml_config['testname'],
      type = 'diskIO',
      name = filename[filename.rfind('\\') + 1:],
      reads = readcount,
      read_bytes = readbytes,
      writes = writecount,
      write_bytes = writebytes
    )
  
  def post(self):
    if (self.testGroup != None):
      self.testGroup.submit() 


def filterOutHeader(data):
  # -1 means we have not yet found the header
  # 0 means we are in the header
  # 1+ means that we are past the header
  state = -1
  for row in data:
    if (len(row) == 0):
      continue

    # Keep looking for the header (denoted by "StartHeader").
    if (row[0] == "StartHeader"):
      state = 0
      continue

    # Eventually, we'll find the end (denoted by "EndHeader").
    if (row[0] == "EndHeader"):
      state = 1
      continue

    if (state == 0):
      addHeader(row[EVENTNAME_INDEX], row)
      continue

    state = state + 1

    # The line after "EndHeader" is also not useful, so we want to strip that
    # in addition to the header.
    if (state > 2):
      yield row

def getIndex(eventType, colName):
  if (colName not in gHeaders[eventType]):
    return None

  return gHeaders[eventType].index(colName)

def readFile(filename):
  print "in readfile: %s" % filename
  data = csv.reader(open(filename, 'rb'), delimiter=',', quotechar='"', skipinitialspace = True)
  data = filterOutHeader(data)
  return data

def fileSummary(row, retVal):
  event = row[EVENTNAME_INDEX]

  #TODO: do we care about the other events?
  if not (event == "FileIoRead" or event == "FileIoWrite"):
    return
  fname_index = getIndex(event, FNAME_COL)

  # We only care about events that have a file name.
  if (fname_index == None):
    return

  # Some data rows are missing the filename?
  if (len(row) <= fname_index):
    return
  
  if (row[fname_index] not in retVal):
    retVal[row[fname_index]] = {"DiskReadBytes": 0, "DiskReadCount": 0, "DiskWriteBytes": 0, "DiskWriteCount": 0}

  if (event == "FileIoRead"):
    retVal[row[fname_index]]['DiskReadCount'] += 1
    idx = getIndex(event, DISKBYTES_COL)
    retVal[row[fname_index]]['DiskReadBytes'] += int(row[idx], 16)
  elif (event == "FileIoWrite"):
    retVal[row[fname_index]]['DiskWriteCount'] += 1
    idx = getIndex(event, DISKBYTES_COL)
    retVal[row[fname_index]]['DiskWriteBytes'] += int(row[idx], 16)

def etl2csv(options):
  """
    Convert etl_filename to etl_filename.csv (temp file) which is the .csv representation of the .etl file
    Etlparser will read this .csv and parse the information we care about into the final output.
    This is done to keep things simple and to preserve resources on talos machines (large files == high memory + cpu)
  """
  
  xperf_cmd = '"%s" -merge %s.user %s.kernel %s' % \
              (options.xperf_path, 
               options.etl_filename,
               options.etl_filename,
               options.etl_filename)
             
  if (options.debug_level >= xtalos.DEBUG_INFO):
    print "executing '%s'" % xperf_cmd
  subprocess.call(xperf_cmd)

  processing_options = []
  xperf_cmd = '"%s" -i %s -o %s.csv %s' % \
              (options.xperf_path,
               options.etl_filename,
               options.etl_filename,
               " -a ".join(processing_options))

  if (options.debug_level >= xtalos.DEBUG_INFO):
    print "executing '%s'" % xperf_cmd
  subprocess.call(xperf_cmd)
  return options.etl_filename + ".csv"

def trackThread(row, firefoxPID):
  event, proc, tid = row[EVENTNAME_INDEX], row[PROCESS_INDEX], row[THREAD_ID_INDEX]
  if event in ["T-DCStart", "T-Start"]:
    procName, procID = re.search("^(.*) \(\s*(\d+)\)$", proc).group(1, 2)
    if procID == firefoxPID:
      imgIdx = getIndex(event, IMAGEFUNC_COL)      
      img = re.match("([^!]+)!", row[imgIdx]).group(1)
      if img == procName:
        gThreads[tid] = "main"
      else:
        "non-main"
  elif event in ["T-DCEnd", "T-End"] and tid in gThreads:
    del gThreads[tid]

def trackThreadFileIO(row, io, stage):
  event, tid = row[EVENTNAME_INDEX], row[THREAD_ID_INDEX]
  opType = {"FileIoWrite": "write", "FileIoRead": "read"}[event]
  th, stg = gThreads[tid], stages[stage]
  sizeIdx = getIndex(event, DISKBYTES_COL)
  bytes = int(row[sizeIdx], 16)
  io[(th, stg, "file_%s_ops" % opType)] = io.get((th, stg, "file_%s_ops" % opType), 0) + 1
  io[(th, stg, "file_%s_bytes" % opType)] = io.get((th, stg, "file_%s_bytes" % opType), 0) + bytes
  io[(th, stg, "file_io_bytes")] = io.get((th, stg, "file_io_bytes"), 0) + bytes

def trackThreadNetIO(row, io, stage):
  event, tid = row[EVENTNAME_INDEX], row[THREAD_ID_INDEX]
  connIdIdx = getIndex(event, ACTIVITY_ID_COL)
  connID = row[connIdIdx]
  if connID not in gConnectionIDs:
    gConnectionIDs[connID] = tid
  origThread = gConnectionIDs[connID]
  if origThread in gThreads:
    netEvt = re.match("[\w-]+\/([\w-]+)", event).group(1) 
    if netEvt in net_events:
      opType = net_events[netEvt]  
      th, stg = gThreads[origThread], stages[stage]
      lenIdx = getIndex(event, NUMBYTES_COL)
      bytes = int(row[lenIdx])
      io[(th, stg, "net_%s_bytes" % opType)] = io.get((th, stg, "net_%s_bytes" % opType), 0) + bytes
      io[(th, stg, "net_io_bytes")] = io.get((th, stg, "net_io_bytes"), 0) + bytes
 
def updateStage(row, stage):
  guidIdx = getIndex(row[EVENTNAME_INDEX], EVENTGUID_COL)
  if row[guidIdx] == CEVT_WINDOWS_RESTORED and stage == 0: stage = 1
  elif row[guidIdx] == CEVT_XPCOM_SHUTDOWN and stage == 1: stage = 2
  return stage

def main():
  parser = xtalos.XtalosOptions()
  options, args = parser.parse_args()
  options = parser.verifyOptions(options)
  if options == None:
    print "Unable to verify options"
    sys.exit(1)

  if not options.processID:
    print "No process ID option given"
    sys.exit(1)

  if options.outputFile:
    outputFile = open(options.outputFile, 'w')

  files = {}
  io = {}
  stage = 0
  
  csvname = etl2csv(options)
  for row in readFile(csvname):
    event = row[EVENTNAME_INDEX]
    if event in ["T-DCStart", "T-Start", "T-DCEnd", "T-End"]:   
      trackThread(row, options.processID)
    elif event in ["FileIoRead", "FileIoWrite"] and row[THREAD_ID_INDEX] in gThreads:
      fileSummary(row, files)  
      trackThreadFileIO(row, io, stage)
    elif event.endswith("Event/Classic") and row[THREAD_ID_INDEX] in gThreads:
      stage = updateStage(row, stage)
    elif event.startswith("Microsoft-Windows-TCPIP"):
      trackThreadNetIO(row, io, stage)

  try:
    os.remove(csvname)
  except:
    pass

  output = "thread, stage, counter, value\n"
  for cntr in sorted(io.iterkeys()):
    output += "%s, %s\n" % (", ".join(cntr), str(io[cntr]))
  if options.outputFile:
    fname = "%s_thread_stats%s" % os.path.splitext(options.outputFile) 
    f = open(fname, "w"); f.write(output); f.close()
  else:
    print output

  header = "filename, readcount, readbytes, writecount, writebytes"
  if options.outputFile:
    outputFile.write(header + "\n")
  else:
    print header
    
  alog = None  
  if options.configFile:
    alog = XPerfAutoLog(options.configFile)
  
  for row in files:
    output = "%s, %s, %s, %s, %s" % \
        (row,
         files[row]['DiskReadCount'],
         files[row]['DiskReadBytes'],
         files[row]['DiskWriteCount'],
         files[row]['DiskWriteBytes'])
         
    if alog:
      alog.addData(row,
         files[row]['DiskReadCount'],
         files[row]['DiskReadBytes'],
         files[row]['DiskWriteCount'],
         files[row]['DiskWriteBytes'])

    if options.outputFile:
      outputFile.write(output + "\n")
    else:
      print output

  if alog:
    alog.post()

  if options.outputFile:
    outputFile.close()

if __name__ == "__main__":
  main()
