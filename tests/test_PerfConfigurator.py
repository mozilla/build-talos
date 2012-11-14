#!/usr/bin/env python

"""
Tests for PerfConfigurator.py

Classes:
    PerfConfiguratorUnitTest
        A class inheriting from unittest.TestCase to test the
        PerfConfigurator class.

        Methods:
        - test_cli
        Tests PerfConfigurator command line interface.

"""

import os
import tempfile
import unittest

from talos.PerfConfigurator import PerfConfigurator
from talos.configuration import YAML

# globals
here = os.path.dirname(os.path.abspath(__file__))
ffox_path = 'test/path/to/firefox'

class PerfConfiguratorUnitTest(unittest.TestCase):
    """
    A class inheriting from unittest.TestCase to test the PerfConfigurator class.
    """

    def test_cli(self):
        """
        Tests PerfConfigurator command line interface.

        This test simulates a call to the PerfConfigurator class from the
        command line interface with a sample of typical options that are
        available to the user.
        It is then tested if the given variables are correctly written into
        options, self.config and into a generated yaml file as output.

        For an explanation of the options given, see PerfConfigurator.py

        """

        example = PerfConfigurator()

        # parse the standard commands
        outfile = tempfile.mktemp(suffix='.yaml')
        options, args = example.parse_args(['--activeTests', 'ts', '--develop',  '-e', ffox_path, '-o', outfile])
        self.assertTrue(os.path.exists(outfile))

        # ensure that the options appropriately get set
        self.assertEqual(bool(args), False) # no arguments
        self.assertEqual(options.develop, True)
        self.assertEqual(options.activeTests, 'ts')
        self.assertEqual(options.browser_path, ffox_path)

        # ensure that the configuration appropriately gets updated
        self.assertEqual(example.config['develop'], True)
        self.assertEqual(example.config['browser_path'], ffox_path)
        self.assertEqual(example.config['tests'][0]['name'], 'ts')

        # ensure that the yaml information are accurate with respect to the data given
        yaml = YAML()
        content = yaml.read(outfile)
        self.assertEqual(content['browser_path'], ffox_path)
        self.assertEqual(content['tests'][0]['name'], 'ts')
        self.assertEqual(content['develop'], True)

        # cleanup
        os.remove(outfile)

if __name__ == '__main__':
    unittest.main()
