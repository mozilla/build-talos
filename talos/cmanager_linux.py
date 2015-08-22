# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import os
import re
import subprocess
import psutil

from cmanager import CounterManager
from mozprocess import pid as mozpid


def xrestop(binary='xrestop'):
    """
    python front-end to running xrestop:
    http://www.freedesktop.org/wiki/Software/xrestop

    For each monitored process, `xrestop -m 1 -b` produces output like:

    0 - Thunderbird ( PID: 2035 ):
        res_base      : 0x1600000
        res_mask      : 0x1fffff
        windows       : 69
        GCs           : 35
        fonts         : 1
        pixmaps       : 175
        pictures      : 272
        glyphsets     : 73
        colormaps     : 0
        passive grabs : 0
        cursors       : 9
        unknowns      : 42
        pixmap bytes  : 4715737
        other bytes   : ~13024
        total bytes   : ~4728761
    """

    process_regex = re.compile(r'([0-9]+) - (.*) \( PID: *(.*) *\):')

    args = ['-m', '1', '-b']
    command = [binary] + args
    process = subprocess.Popen(command,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()
    if process.returncode:
        raise Exception(
            "Unexpected error executing '%s':\n%s"
            % (subprocess.list2cmdline(command), stdout)
        )

    # process output
    retval = {}
    index = name = pid = None
    for line in stdout.strip().splitlines():
        line = line.rstrip()
        match = process_regex.match(line)
        if match:
            index, name, pid = match.groups()
            try:
                pid = int(pid)
            except ValueError:
                # ignore processes without PIDs
                index = name = pid = None
                continue
            index = int(index)
            retval[pid] = dict(index=index, name=name)
        else:
            if not pid:
                continue
            counter, value = line.split(':', 1)
            counter = counter.strip()
            value = value.strip()
            retval[pid][counter] = value

    return retval


def GetPrivateBytes(pids):
    """Calculate the amount of private, writeable memory allocated to a
       process.
       This code was adapted from 'pmap.c', part of the procps project.
    """
    privateBytes = 0
    for pid in pids:
        mapfile = '/proc/%s/maps' % pid
        with open(mapfile) as maps:

            private = 0

            for line in maps:
                # split up
                (range, line) = line.split(" ", 1)

                (start, end) = range.split("-")
                flags = line.split(" ", 1)[0]

                size = int(end, 16) - int(start, 16)

                if flags.find("p") >= 0:
                    if flags.find("w") >= 0:
                        private += size

            privateBytes += private

    return privateBytes


def GetResidentSize(pids):
    """Retrieve the current resident memory for a given process"""
    # for some reason /proc/PID/stat doesn't give accurate information
    # so we use status instead

    RSS = 0
    for pid in pids:
        file = '/proc/%s/status' % pid

        with open(file) as status:

            for line in status:
                if line.find("VmRSS") >= 0:
                    RSS += int(line.split()[1]) * 1024

    return RSS


def GetXRes(pids):
    """Returns the total bytes used by X or raises an error if total bytes
    is not available"""
    XRes = 0
    xres_output = xrestop()
    for pid in pids:
        if pid in xres_output:
            data = xres_output[pid]['total bytes']
            data = data.lstrip('~')  # total bytes is like '~4728761'
            try:
                data = float(data)
                XRes += data
            except ValueError:
                print "Invalid data, not a float"
                raise
        else:
            raise Exception("Could not find PID=%s in xrestop output" % pid)
    return XRes


def GetNetworkCounters(counterName):
    args = {
       "Network_lo_packets_rx": ('lo', 'packets_recv'),
       "Network_lo_packets_tx": ('lo', 'packets_sent'),
       "Network_lo_bytes_rx": ('lo', 'bytes_recv'),
       "Network_lo_bytes_tx": ('lo', 'bytes_sent'),
       "Network_eth0_packets_rx": ('eth0', 'packets_recv'),
       "Network_eth0_packets_tx": ('eth0', 'packets_sent'),
       "Network_eth0_bytes_rx": ('eth0', 'bytes_recv'),
       "Network_eth0_bytes_tx": ('eth0', 'bytes_sent')
    }
    nic, field = args[counterName]
    counters = psutil.net_io_counters(pernic=True)
    data = counters[nic]
    fields = ['bytes_sent', 'bytes_recv', 'packets_sent', 'packets_recv', 'errin', 'errout', 'dropin', 'dropout']
    idx = fields.index(field)
    return data[idx]


class LinuxCounterManager(CounterManager):
    """This class manages the monitoring of a process with any number of
       counters.

       A counter can be any function that takes an argument of one pid and
       returns a piece of data about that process.
       Some examples are: CalcCPUTime, GetResidentSize, and GetPrivateBytes
    """

    counterDict = {"Private Bytes": GetPrivateBytes,
                   "RSS": GetResidentSize,
                   "XRes": GetXRes,
                   "Network_lo_packets_rx": GetNetworkCounters,
                   "Network_lo_packets_tx": GetNetworkCounters,
                   "Network_lo_bytes_rx": GetNetworkCounters,
                   "Network_lo_bytes_tx": GetNetworkCounters,
                   "Network_eth0_packets_rx": GetNetworkCounters,
                   "Network_eth0_packets_tx": GetNetworkCounters,
                   "Network_eth0_bytes_rx": GetNetworkCounters,
                   "Network_eth0_bytes_tx": GetNetworkCounters}

    def __init__(self, process, counters=None,
                 childProcess="plugin-container"):
        """Args:
             counters: A list of counters to monitor. Any counters whose name
             does not match a key in 'counterDict' will be ignored.
        """

        CounterManager.__init__(self)
        self.childProcess = childProcess
        self.pidList = []
        self.primaryPid = mozpid.get_pids(process)[-1]
        os.stat('/proc/%s' % self.primaryPid)

        self._loadCounters()
        self.registerCounters(counters)

    def getCounterValue(self, counterName):
        """Returns the last value of the counter 'counterName'"""
        try:
            self.updatePidList()
            if counterName.startswith('Network'):
                return self.registeredCounters[counterName][0](counterName)
            else:
                return self.registeredCounters[counterName][0](self.pidList)
        except:
            return None

    def updatePidList(self):
        """Updates the list of PIDs we're interested in"""
        try:
            self.pidList = [self.primaryPid]
            childPids = mozpid.get_pids(self.childProcess)
            for pid in childPids:
                os.stat('/proc/%s' % pid)
                self.pidList.append(pid)
        except:
            print "WARNING: problem updating child PID's"
