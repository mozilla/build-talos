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

#required for the autolog stuff
import yaml
import time
from mozautolog import RESTfulAutologTestGroup

EVENTNAME_INDEX = 0
DISKBYTES_COL = "Size"
FNAME_COL = "FileName"

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
  retVal = []
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
      retVal.append(row)
  return retVal

def getIndex(eventType, colName):
  if (colName not in gHeaders[eventType]):
    return None

  return gHeaders[eventType].index(colName)

def readFile(filename, procName = None):
  if (procName):
    filename = filterByProcName(filename, procName)

  print "in readfile: %s, %s" % (filename, procName)
  data = csv.reader(open(filename, 'rb'), delimiter=',', quotechar='"', skipinitialspace = True)
  data = filterOutHeader(data)

  return data

#for large files we need to read chunk by chunk and filter into a temporary file
def filterByProcName(filename, procname):
  ffx = re.compile('.*\,\s+' + procname + '.*')
  cache = open(filename + ".part", 'w')
  f = open(filename, 'r')
  data = f.read(4096)
  lastline = '' #used for reads that are partial lines
  headers = False
  while (data != ""):  
    lines = data.split('\n')
    for line in lines:
      if (line == lines[-1]):
        lastline = lines[-1]
        continue
      elif (lastline != ''):
        line = "%s%s" % (lastline, line)
        lastline = ''
        
      if (headers is False):
        if re.match('.*EndHeader.*', line):
          headers = True
        cache.write(line + "\n")
      elif ffx.match(line):
        cache.write(line + "\n")
    #TODO: ensure our lastline isn't counted twice and valid
    lastline = lines[-1]
    data = f.read(4096)
  cache.write(lastline + "\n")
  
  f.close()
  cache.close()
  return filename + '.part'

def fileSummary(data):
  retVal = {}
  for row in data:
    if (len(row) > EVENTNAME_INDEX):      
      event = row[EVENTNAME_INDEX]

      #TODO: do we care about the other events?
      if not (event == "FileIoRead" or event == "FileIoWrite"):
        continue
      fname_index = getIndex(event, FNAME_COL)
      
      # We only care about events that have a file name.
      if (fname_index == None):
        continue

      # Some data rows are missing the filename?
      if (len(row) <= fname_index):
        continue
      
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

  return retVal

def etl2csv(options):
  """
    Convert etl_filename to etl_filename.csv (temp file) which is the .csv representation of the .etl file
    Etlparser will read this .csv and parse the information we care about into the final output.
    This is done to keep things simple and to preserve resources on talos machines (large files == high memory + cpu)
  """
  
  processing_options = []
  xperf_cmd = '"%s" -i %s -o %s.csv %s' % \
              (options.xperf_path,
               options.etl_filename,
               options.etl_filename,
               " -a ".join(processing_options))

  if (options.debug_level >= xtalos.DEBUG_INFO):
    print "executing '%s'" % xperf_cmd
  os.system(xperf_cmd)
  return options.etl_filename + ".csv"

def main():
  parser = xtalos.XtalosOptions()
  options, args = parser.parse_args()
  options = parser.verifyOptions(options)
  if options == None:
    print "Unable to verify options"
    sys.exit(1)

  if options.outputFile:
    outputFile = open(options.outputFile, 'w')


  csvname = etl2csv(options)
  data = readFile(csvname, options.processName)
  files = fileSummary(data)
  try:
    os.remove(csvname)
    os.remove(csvname + ".part")
  except:
    pass

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
