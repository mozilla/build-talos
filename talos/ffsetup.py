# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""A set of functions to set up a browser with the correct
   preferences and extensions in the given directory.

"""

import os
import re
import tempfile
import time
import glob
from mozprofile.profile import Profile

from utils import TalosError, MakeDirectoryContentsWritable
import utils

import TalosProcess


class FFSetup(object):

    _remoteWebServer = 'localhost'
    _deviceroot = ''
    _host = ''
    _port = ''
    _hostproc = None

    def __init__(self, procmgr, options=None):
        self.ffprocess = procmgr
        self._hostproc = procmgr
        if options is not None:
            self.intializeRemoteDevice(options)
        self.extensions = None

    def initializeRemoteDevice(self, options, hostproc=None):
        self._remoteWebServer = options['webserver']
        self._deviceroot = options['deviceroot']
        self._host = options['host']
        self._port = options['port']
        self._env = options['env']
        self._hostproc = hostproc or self.ffprocess

    def PrefString(self, name, value, newline):
        """Helper function to create a pref string for profile prefs.js
            in the form 'user_pref("name", value);<newline>'

        Args:
            name: String containing name of pref
            value: String containing value of pref
            newline: Line ending to use, i.e. '\n' or '\r\n'

        Returns:
            String containing 'user_pref("name", value);<newline>'
        """

        out_value = str(value)
        if type(value) == bool:
            # Write bools as "true"/"false", not "True"/"False".
            out_value = out_value.lower()
        if type(value) == str:
            # Write strings with quotes around them.
            out_value = '"%s"' % value
        return 'user_pref("%s", %s);%s' % (name, out_value, newline)

    def CreateTempProfileDir(self, source_profile, prefs, extensions,
                             webserver):
        """Creates a temporary profile directory from the source profile
            directory and adds the given prefs and links to extensions.

        Args:
            source_profile: String containing the absolute path of the source
                            profile directory to copy from.
            prefs: Preferences to set in the prefs.js file of the new profile.
                    Format: {"PrefName1" : "PrefValue1",
                    "PrefName2" : "PrefValue2"}
            extensions: list of paths to .xpi files to be installed

        Returns:
            String containing the absolute path of the profile directory.
        """

        # Create a temporary directory for the profile, and copy the
        # source profile to it.
        temp_dir = tempfile.mkdtemp()
        profile_dir = os.path.join(temp_dir, 'profile')
        profile = Profile.clone(source_profile, profile_dir)
        MakeDirectoryContentsWritable(profile_dir)

        # Copy the user-set prefs to user.js
        real_prefs = {}
        for name, value in prefs.iteritems():
            if type(value) is str:
                webserver_var = webserver
                if '://' not in webserver:
                    webserver_var = 'http://' + webserver_var
                value = utils.interpolate(value, webserver=webserver_var)
            real_prefs[name] = value
        profile.set_preferences(real_prefs)

        if (webserver and webserver != 'localhost'):
            self.ffprocess.addRemoteServerPref(profile_dir, webserver)

        # Install the extensions.
        profile.addon_manager.install_addons(extensions)

        if webserver != 'localhost' and self._host != '':
            remote_dir = self.ffprocess.copyDirToDevice(profile_dir)
            profile_dir = remote_dir
        return temp_dir, profile_dir

    def InstallInBrowser(self, browser_path, dir_path):
        """
            Take the given directory and copies it to appropriate location in
            the given browser install
        """
        # add the provided directory to the given browser install
        fromfiles = glob.glob(os.path.join(dir_path, '*'))
        todir = os.path.join(os.path.dirname(browser_path),
                             os.path.basename(os.path.normpath(dir_path)))
        for fromfile in fromfiles:
            self.ffprocess.copyFile(fromfile, todir)

    def InitializeNewProfile(self, profile_dir, browser_config):
        """
        Runs browser with the new profile directory, to negate any performance
        hit that could occur as a result of starting up with a new profile.
        Also kills the "extra" browser that gets spawned the first time browser
        is run with a new profile.
        Returns 1 (success) if PROFILE_REGEX is found,
        and 0 (failure) otherwise

        Args:
            browser_config: object containing all the browser_config options
            profile_dir: The full path to the profile directory to load
        """
        PROFILE_REGEX = re.compile('__metrics(.*)__metrics',
                                   re.DOTALL | re.MULTILINE)

        command_args = utils.GenerateBrowserCommandLine(
            browser_config["browser_path"],
            browser_config["extra_args"],
            browser_config["deviceroot"],
            profile_dir,
            browser_config["init_url"]
        )
        pid = None
        if not browser_config['remote']:
            browser = TalosProcess.TalosProcess(
                command_args,
                env=os.environ.copy(),
                logfile=browser_config['browser_log']
            )
            browser.run()
            pid = browser.pid
            try:
                browser.wait()
            except KeyboardInterrupt:
                browser.kill()
                raise
            finally:
                browser.closeLogFile()
            browser = None
            time.sleep(5)
        else:
            self.ffprocess.runProgram(browser_config, command_args,
                                      timeout=1200)

        res = 0
        if not os.path.isfile(browser_config['browser_log']):
            raise TalosError("initalization has no output from browser")
        results_file = open(browser_config['browser_log'], "r")
        results_raw = results_file.read()
        results_file.close()

        match = PROFILE_REGEX.search(results_raw)
        if match:
            res = 1
        else:
            utils.info("Could not find %s in browser_log: %s",
                       PROFILE_REGEX.pattern, browser_config['browser_log'])
            utils.info("Raw results:%s", results_raw)
            utils.info("Initialization of new profile failed")

        return res, pid
