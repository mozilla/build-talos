#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import csv
import re
import os
import optparse
import sys
import xtalos
import subprocess

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


def filterOutHeader(data):
    # -1 means we have not yet found the header
    # 0 means we are in the header
    # 1+ means that we are past the header
    state = -1
    for row in data:

        if not len(row):
            continue

        # Keep looking for the header (denoted by "StartHeader").
        if row[0] == "StartHeader":
            state = 0
            continue

        # Eventually, we'll find the end (denoted by "EndHeader").
        if row[0] == "EndHeader":
            state = 1
            continue

        if state == 0:
            gHeaders[row[EVENTNAME_INDEX]] = row
            continue

        state = state + 1

        # The line after "EndHeader" is also not useful, so we want to strip that
        # in addition to the header.
        if state > 2:
            yield row

def getIndex(eventType, colName):
    if colName not in gHeaders[eventType]:
        return None
    return gHeaders[eventType].index(colName)

def readFile(filename):
    print "etlparser: in readfile: %s" % filename
    data = csv.reader(open(filename, 'rb'), delimiter=',', quotechar='"', skipinitialspace=True)
    data = filterOutHeader(data)
    return data

def fileSummary(row, retVal):
    event = row[EVENTNAME_INDEX]

    # TODO: do we care about the other events?
    if not event in ("FileIoRead", "FileIoWrite"):
        return
    fname_index = getIndex(event, FNAME_COL)

    # We only care about events that have a file name.
    if fname_index is None:
        return

    # Some data rows are missing the filename?
    if len(row) <= fname_index:
        return

    if row[fname_index] not in retVal:
        retVal[row[fname_index]] = {"DiskReadBytes": 0, "DiskReadCount": 0, "DiskWriteBytes": 0, "DiskWriteCount": 0}

    if event == "FileIoRead":
        retVal[row[fname_index]]['DiskReadCount'] += 1
        idx = getIndex(event, DISKBYTES_COL)
        retVal[row[fname_index]]['DiskReadBytes'] += int(row[idx], 16)
    elif event == "FileIoWrite":
        retVal[row[fname_index]]['DiskWriteCount'] += 1
        idx = getIndex(event, DISKBYTES_COL)
        retVal[row[fname_index]]['DiskWriteBytes'] += int(row[idx], 16)

def etl2csv(xperf_path, etl_filename, debug=False):
    """
    Convert etl_filename to etl_filename.csv (temp file) which is the .csv representation of the .etl file
    Etlparser will read this .csv and parse the information we care about into the final output.
    This is done to keep things simple and to preserve resources on talos machines (large files == high memory + cpu)
    """

    xperf_cmd = [xperf_path,
                 '-merge',
                 '%s.user' % etl_filename,
                 '%s.kernel' % etl_filename,
                 etl_filename]
    if debug:
        print "executing '%s'" % subprocess.list2cmdline(xperf_cmd)
    subprocess.call(xperf_cmd)

    csv_filename = '%s.csv' % etl_filename
    xperf_cmd = [xperf_path,
                 '-i', etl_filename,
                 '-o', csv_filename]
    if debug:
        print "executing '%s'" % subprocess.list2cmdline(xperf_cmd)
    subprocess.call(xperf_cmd)
    return csv_filename

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
                gThreads[tid] = "nonmain"
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
    if row[guidIdx] == CEVT_WINDOWS_RESTORED and stage == 0:
        stage = 1
    elif row[guidIdx] == CEVT_XPCOM_SHUTDOWN and stage == 1:
        stage = 2
    return stage

def etlparser(xperf_path, etl_filename, processID, configFile=None, outputFile=None, debug=False):

    # setup output file
    if outputFile:
        outFile = open(outputFile, 'w')
    else:
        outFile = sys.stdout

    files = {}
    io = {}
    stage = 0

    csvname = etl2csv(xperf_path, etl_filename, debug=debug)
    for row in readFile(csvname):
        event = row[EVENTNAME_INDEX]
        if event in ["T-DCStart", "T-Start", "T-DCEnd", "T-End"]:
            trackThread(row, processID)
        elif event in ["FileIoRead", "FileIoWrite"] and row[THREAD_ID_INDEX] in gThreads:
            fileSummary(row, files)
            trackThreadFileIO(row, io, stage)
        elif event.endswith("Event/Classic") and row[THREAD_ID_INDEX] in gThreads:
            stage = updateStage(row, stage)
        elif event.startswith("Microsoft-Windows-TCPIP"):
            trackThreadNetIO(row, io, stage)

    # remove the csv file
    try:
        os.remove(csvname)
    except:
        pass

    output = "thread, stage, counter, value\n"
    for cntr in sorted(io.iterkeys()):
        output += "%s, %s\n" % (", ".join(cntr), str(io[cntr]))
    if outputFile:
        fname = "%s_thread_stats%s" % os.path.splitext(outputFile)
        f = open(fname, "w")
        f.write(output)
        f.close()
    else:
        print output

    header = "filename, readcount, readbytes, writecount, writebytes"
    outFile.write(header + "\n")

    # output data
    for row in files:
        output = "%s, %s, %s, %s, %s" % (row,
                                         files[row]['DiskReadCount'],
                                         files[row]['DiskReadBytes'],
                                         files[row]['DiskWriteCount'],
                                         files[row]['DiskWriteBytes'])
        outFile.write(output + "\n")

    if outputFile:
        # close the file handle
        outFile.close()

def etlparser_from_config(config_file, **kwargs):
    """start from a YAML config file"""

    # option defaults
    args = {'xperf_path': 'xperf.exe',
            'etl_filename': 'output.etl',
            'outputFile': None,
            'processID': None
            }
    args.update(kwargs)

    # override from YAML config file
    args = xtalos.options_from_config(args, config_file)

    # ensure process ID is given
    if not args.get('processID'):
        raise xtalos.xtalosError("No process ID option given")

    # ensure path to xperf given
    if not os.path.exists(args['xperf_path']):
        raise xtalos.xtalosError("ERROR: xperf_path '%s' does not exist" % args['xperf_path'])

    # update args with config file
    args['configFile'] = config_file

    # call etlparser
    etlparser(**args)

def main(args=sys.argv[1:]):

    # parse command line options
    parser = xtalos.XtalosOptions()
    options, args = parser.parse_args(args)
    options = parser.verifyOptions(options)
    if options == None:
        parser.error("Unable to verify options")
    if not options.processID:
        parser.error("No process ID option given")

    # call API
    etlparser(options.xperf_path, options.etl_filename, options.processID,
              options.configFile, options.outputFile,
              debug=options.debug_level >= xtalos.DEBUG_INFO)

if __name__ == "__main__":
    main()
