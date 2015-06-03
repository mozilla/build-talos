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
        - test_errors
        Tests if errors and exceptions are correctly raised.
        - assertError
        Asserts if a specific error is raised on specific incorrect input into Perfconfigurator.

"""

import os
import tempfile
import unittest

from talos.PerfConfigurator import PerfConfigurator, ConfigurationError
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
        args = example.parse_args(['--activeTests', 'ts_paint', '--develop',  '-e', ffox_path, '-o', outfile])
        self.assertTrue(os.path.exists(outfile))

        # ensure that the options appropriately get set
        self.assertEqual(bool(args.configuration_files), False) # no arguments
        self.assertEqual(args.develop, True)
        self.assertEqual(args.activeTests, 'ts_paint')
        self.assertEqual(args.browser_path, ffox_path)

        # ensure that the configuration appropriately gets updated
        self.assertEqual(example.config['develop'], True)
        self.assertEqual(example.config['browser_path'], ffox_path)
        self.assertEqual(example.config['tests'][0]['name'], 'ts_paint')

        # ensure that the yaml information are accurate with respect to the data given
        yaml = YAML()
        content = yaml.read(outfile)
        self.assertEqual(content['browser_path'], ffox_path)
        self.assertEqual(content['tests'][0]['name'], 'ts_paint')
        self.assertEqual(content['develop'], True)

        # cleanup
        os.remove(outfile)

    def test_errors(self):
        """
        Tests if errors and exceptions are correctly raised.
        Excludes tests for remote machines.

        """
        self.example = PerfConfigurator()

        faults = []
        outfile = tempfile.mktemp(suffix='.yaml')
        error_tests = {'--activeTests':{'error':ConfigurationError,
                                        'args':['--activeTests', 'badtest', '--develop', '-e', ffox_path, "-o", outfile],
                                        'except_fault' : 'invalid --activeTest raised an error that is not ConfigurationError',
                                        'non_raises_fault' : 'invalid --activeTest passed test'},
                       '--fennecIDs':{'error':ConfigurationError,
                                      'args':['--activeTests', 'ts_paint', '--develop', '-e', ffox_path, '--fennecIDs', ffox_path, "-o", outfile],
                                      'except_fault' : 'invalid --fennecIDs raised an error that is not ConfigurationError',
                                      'non_raises_fault' : 'invalid --fennecIDs passed test'},
                       '--fennecIDs':{'error':ConfigurationError,
                                      'args':['--activeTests', 'ts_paint', '--develop', '-e', ffox_path, '--fennecIDs', 'filedoesnotexist.txt', "-o", outfile],
                                      'except_fault' : 'invalid --fennecIDs raised an error that is not ConfigurationError',
                                      'non_raises_fault' : 'invalid --fennecIDs passed test'},
                       '--filter':{'error':ConfigurationError,
                                   'args' : ['--activeTests', 'ts_paint', '--develop',  '-e', ffox_path, '--filter', 'badfilter', '-o', outfile],
                                   'except_fault' : 'invalid --filter raised an error that is not ConfigurationError',
                                   'non_raises_fault' : 'invalid --filter passed test'},
                       '--ignoreFirst':{'error':ConfigurationError,
                                        'args' : ['--activeTests', 'ts_paint', '--develop',  '-e', ffox_path, '--ignoreFirst', '--filter',
                                                  'median', "-o", outfile],
                                        'except_fault' : '--ignoreFirst and --filter raised an error that is not ConfigurationError',
                                        'non_raises_fault' : '--ignoreFirst and --filter together passed test '\
                                                             '(Should raise ConfigurationError when called together)'},
                       '--remoteDevice':{'error':BaseException,
                                         'args':['--activeTests', 'ts_paint', '--develop',  '-e', ffox_path,'--remoteDevice', '0.0.0.0',
                                                 '-o', outfile],
                                         'except_fault':'invalid --remoteDevice raised an error that is not BaseException',
                                         'non_raise_fault':'invalid --remoteDevice passed test'},
                       }

        # Taken from http://k0s.org/mozilla/hg/configuration/file/56db0b2b90af/tests/unit.py
        error_msg = []
        def error(msg):
            error_msg.append(msg)
        self.example.error = error

        # no firefox path and no tests given
        self.example.parse_args(args=["-o", outfile])
        self.assertEqual(error_msg, ["Please specify --executablePath",
                                     "No tests found; please specify --activeTests"])

        for test, parameters in error_tests.items():
            result = self.assertError(self.example, parameters)
            if result == None:
                pass
            else:
                faults.append(result)

        # in PerfConfigurator method 'tests(self, activeTests, overrides=None, global_overrides=None, counters=None)'
        # invalid test given
        try:
            self.example.tests(['badtest'])
            faults.append("example.tests(['badtest']) passed test")
        except ConfigurationError:
            pass
        except:
            faults.append("example.tests(['badtest']) raised an error that is not ConfigurationError")

        # invalid overrides
        try:
            self.example.tests(['ts_paint'], overrides={'ts_paint':'not a dict'})
            faults.append("example.tests(['ts_paint'], overrides={'ts_paint':'not a dict') passed test")
        except ConfigurationError:
            pass
        except:
            faults.append("example.tests(['ts_paint'], overrides={'ts_paint':'not a dict') raised an error that is not ConfigurationError")

        # Test to see if all errors were raised correctly
        self.assertEqual(faults, [])

        # clean-up
        os.remove(outfile)

    def assertError(self, p_configurator, error_test_dict):
        """
        Asserts if a specific error is raised on specific incorrect input into Perfconfigurator.
        """
        try:
            args = p_configurator.parse_args(error_test_dict['args'])
        except error_test_dict['error']:
            return None
        except:
            return error_test_dict['except_fault']
        return error_test_dict['non_raises_fault']

if __name__ == '__main__':
    unittest.main()
