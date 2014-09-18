#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import os
import sys
import imp
import unittest

tests_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tests')
testfiles = [os.path.join(tests_dir, i) for i in os.listdir(tests_dir) if i.endswith('.py')]

def unittests(path):
    """return the unittests in a .py file"""
    path = os.path.abspath(path)
    unittests = []
    assert os.path.exists(path)
    directory = os.path.dirname(path)
    sys.path.insert(0, directory) # insert directory into path for top-level imports
    modname = os.path.splitext(os.path.basename(path))[0]
    print modname
    module = imp.load_source(modname, path)
    sys.path.pop(0) # remove directory from global path
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(module)
    for test in suite:
        unittests.append(test)
    return unittests

def runtests():
    suite = unittest.TestSuite()
    for testfile in testfiles:
        test_path = os.path.join(tests_dir, testfile)
        tests = unittests(os.path.abspath(test_path))
        for test in tests:
            suite.addTest(test)
    failures = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(failures) # Otherwise will crash and burn with a TypeError

if __name__ == '__main__':
    runtests()
