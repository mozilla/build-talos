#!/usr/bin/env python

"""
test installing Talos:
https://bugzilla.mozilla.org/show_bug.cgi?id=709881

requires network access
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import urllib2

# globals
here = os.path.dirname(os.path.abspath(__file__))
#VIRTUALENV='https://raw.github.com/pypa/virtualenv/develop/virtualenv.py'
VIRTUALENV='https://raw.github.com/pypa/virtualenv/1.10/virtualenv.py'

class TalosInstallation(unittest.TestCase):

    def test_install(self):

        # find setup.py
        home = os.path.dirname(here)
        setup_py = os.path.join(home, 'setup.py')
        self.assertTrue(os.path.exists(setup_py))

        # create a virtualenv
        tempdir = tempfile.mkdtemp()
        try:
            python = self.create_virtualenv(tempdir)

            # ensure we can't import Talos
            self.assertCall([python, '-c', 'import talos'], success=False, cwd=tempdir)

            # install Talos into the virtualenv
            self.assertCall([python, setup_py, 'install'], cwd=home)

            # ensure we can import Talos
            self.assertCall([python, '-c', 'import talos'], cwd=tempdir)
            self.assertCall([python, '-c', 'from talos import run_tests'], cwd=tempdir)

        finally:
            # cleanup
            shutil.rmtree(tempdir)

    def assertCall(self, command, success=True, **kw):
        """
        assert that a subshell call succeeds or fails
        """

        kw.setdefault('stdout', subprocess.PIPE)
        kw.setdefault('stderr', subprocess.PIPE)
        process = subprocess.Popen(command, **kw)
        stdout, stderr = process.communicate()
        returncode = process.returncode
        if success:
            check = returncode == 0
        else:
            check = returncode != 0
        if not check:
            for i in ('command', 'kw', 'stdout', 'stderr', 'returncode'):
                print ':%s: %s' % (i, locals()[i])
        self.assertTrue(check)

    def create_virtualenv(self, path):
        """
        make a virtualenv at `path`;
        returns the path to the virtualenv's python,
        or None if something bad happens
        """

        python = None # return value

        # make a temporary copy of virtualenv
        fd, filename = tempfile.mkstemp(suffix='.py')
        try:
            os.write(fd, urllib2.urlopen(VIRTUALENV).read())
            os.close(fd)

            # create a virtualenv via a subshell
            self.assertCall([sys.executable, filename, '--no-site-packages', path])

            # find the python executable
            for subdir, executable in (('bin', 'python'),          # linux + mac
                                       ('Scripts', 'python.exe')): # windows
                scripts = os.path.join(path, subdir)
                if os.path.exists(scripts):
                    python = os.path.join(scripts, executable)
                    self.assertTrue(os.path.exists(python))
        finally:
            # cleanup
            try:
                os.close(fd)
            except:
                pass
            os.remove(filename)

        # returns the path to python executable
        return python

if __name__ == '__main__':
    unittest.main()
