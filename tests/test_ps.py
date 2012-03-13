#!/usr/bin/env python

"""
test talos ps facilities
"""

import os
import subprocess
import sys
import talos.utils
import unittest

# globals
here = os.path.dirname(os.path.abspath(__file__))

class TalosProcess(unittest.TestCase):

    def test_parsing(self):
        # see https://bugzilla.mozilla.org/show_bug.cgi?id=734146#c21

        # read process output
        filename = os.path.join(here, 'ps-Acj.out')
        ps_output = file(filename).read()

        # parse it
        parsed = talos.utils._parse_ps(ps_output)

        # find the CCacheServer entry
        # cltbld     123    94   123 db265f0    1        ??    0:00.00 (CCacheServer)
        line = [i for i in parsed if i['PID'] == '123']
        self.assertEqual(len(line), 1)
        line = line[0]
        self.assertEqual(line['STAT'], '')
        self.assertEqual(line['COMMAND'], '(CCacheServer)')

        # find another entry, let's go with pboard
        line = [i for i in parsed if i['PID'] == '122']
        self.assertEqual(len(line), 1)
        line = line[0]
        self.assertEqual(line['STAT'], 'S')
        self.assertEqual(line['COMMAND'], 'pboard')

    def test_ps(self):

        # create a process with a time delay
        command = [sys.executable, '-c', 'import time; time.sleep(3)']
        process = subprocess.Popen(command)
        pid = process.pid

        # ensure it's running
        self.assertEqual(talos.utils.is_running(pid), True)

        # ensure it shows up in ps
        process_table = talos.utils.ps()
        line = [i for i in process_table if i['PID'] == str(pid)]
        self.assertEqual(len(line), 1)
        line = line[0]
        self.assertEqual(line['COMMAND'], ' '.join(command))

        # ensure it shows up as a running process
        basename = os.path.basename(sys.executable)
        processes = talos.utils.running_processes(basename)
        self.assertTrue(len(processes))
        self.assertTrue(pid in [i[0] for i in processes])

if __name__ == '__main__':
    unittest.main()
