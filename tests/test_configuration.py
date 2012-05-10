#!/usr/bin/env python

"""
test talos configuration
"""

import os
import talos
import talos.PerfConfigurator as PerfConfigurator
import unittest

talos_dir = os.path.dirname(os.path.abspath(talos.__file__))

class TestTalosConfiguration(unittest.TestCase):

    def test_extend(self):
        """test extending configuration from a .config file"""

        # ensure the .config file overrides have made it in
        addon_config = os.path.join(talos_dir, 'addon.config')
        self.assertTrue(os.path.exists(addon_config))
        conf = PerfConfigurator.PerfConfigurator()
        conf.parse_args(['-a', 'ts', '-e', '/opt/bin/firefox', addon_config])
        self.assertTrue('extensions.firebug.net.enableSites' in conf.config['preferences'])

        xperf_config = os.path.join(talos_dir, 'xperf.config')
        self.assertTrue(os.path.exists(xperf_config))
        conf = PerfConfigurator.PerfConfigurator()
        conf.parse_args(['-a', 'ts', '-e', '/opt/bin/firefox', xperf_config])
        self.assertEqual(conf.config['basetest']['tpcycles'], 1) # the default is 10
        self.assertTrue('xperf_stackwalk' in conf.config['basetest'])

if __name__ == '__main__':
    unittest.main()
