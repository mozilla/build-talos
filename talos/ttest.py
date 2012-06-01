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
# The Original Code is standalone Firefox Windows performance test.
#
# The Initial Developer of the Original Code is Google Inc.
# Portions created by the Initial Developer are Copyright (C) 2006
# the Initial Developer. All Rights Reserved.
#
# Contributor(s):
#   Annie Sullivan <annie.sullivan@gmail.com> (original author)
#   Ben Hearsum    <bhearsum@wittydomain.com> (OS independence)
#   Alice Nodelman <anodelman@mozilla.com>
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

"""A generic means of running an URL based browser test
   follows the following steps
     - creates a profile
     - tests the profile
     - gets metrics for the current test environment
     - loads the url
     - collects info on any counters while test runs
     - waits for a 'dump' from the browser
"""

__author__ = 'annie.sullivan@gmail.com (Annie Sullivan)'

import glob
import mozinfo
import os
import platform
import re
import results
import shutil
import sys
import subprocess
import tempfile
import time
import utils

from utils import talosError
from ffprocess_linux import LinuxProcess
from ffprocess_win32 import Win32Process
from ffprocess_mac import MacProcess
from ffsetup import FFSetup

class TTest(object):

    _ffsetup = None
    _ffprocess = None
    platform_type = ''

    def __init__(self, remote = False):
        cmanager, platformtype, ffprocess = self.getPlatformType(remote)
        self.cmanager = cmanager
        self.platform_type = platformtype
        self._ffprocess = ffprocess
        self._hostproc = ffprocess
        self.remote = remote

        self._ffsetup = FFSetup(self._ffprocess)

    def getPlatformType(self, remote):
        cmanager = None
        _ffprocess = None
        if remote == True:
            platform_type = 'remote_'
            import cmanager_remote as cmanager
        elif platform.system() == "Linux":
            import cmanager_linux as cmanager
            platform_type = 'linux_'
            _ffprocess = LinuxProcess()
        elif platform.system() in ("Windows", "Microsoft"):
            if '5.1' in platform.version(): #winxp
                platform_type = 'win_'
            elif '6.1' in platform.version(): #w7
                platform_type = 'w7_'
            else:
                raise talosError('unsupported windows version')
            import cmanager_win32 as cmanager
            _ffprocess = Win32Process()
        elif platform.system() == "Darwin":
            import cmanager_mac as cmanager
            platform_type = 'mac_'
            _ffprocess = MacProcess()
        return cmanager, platform_type, _ffprocess

    def initializeLibraries(self, browser_config):
        if browser_config['remote'] == True:
            cmanager, platform_type, ffprocess = self.getPlatformType(False)

            from ffprocess_remote import RemoteProcess
            self._ffprocess = RemoteProcess(browser_config['host'], 
                                           browser_config['port'], 
                                           browser_config['deviceroot'])
            self._ffsetup = FFSetup(self._ffprocess)
            self._ffsetup.initializeRemoteDevice(browser_config, ffprocess)
            self._hostproc = ffprocess

    def createProfile(self, profile_path, browser_config):
        # Create the new profile
        temp_dir, profile_dir = self._ffsetup.CreateTempProfileDir(profile_path,
                                                     browser_config['preferences'],
                                                     browser_config['extensions'],
                                                     browser_config['webserver'])
        utils.debug("created profile") 
        return profile_dir, temp_dir

    def initializeProfile(self, profile_dir, browser_config):
        if not self._ffsetup.InitializeNewProfile(profile_dir, browser_config):
            raise talosError("failed to initialize browser")
        processes = self._ffprocess.checkAllProcesses(browser_config['process'], browser_config['child_process'])
        if processes:
            raise talosError("browser failed to close after being initialized")

    def cleanupProfile(self, dir):
        # Delete the temp profile directory  Make it writeable first,
        # because every once in a while browser seems to drop a read-only
        # file into it.
        self._hostproc.removeDirectory(dir)

    def cleanupAndCheckForCrashes(self, browser_config, profile_dir):
        cleanup_result = self._ffprocess.cleanupProcesses(browser_config['process'], 
                                                          browser_config['child_process'], 
                                                          browser_config['browser_wait']) 
        if platform.system() in ('Windows', 'Microsoft'):
            stackwalkpaths = ['win32', 'minidump_stackwalk.exe']
        elif platform.system() == 'Linux':
            if platform.machine() == 'armv6l':
                stackwalkpaths = ['maemo', 'minidump_stackwalk']
            elif '64' in platform.architecture()[0]: #are we 64 bit?
                stackwalkpaths = ['linux64', 'minidump_stackwalk']
            else:
                stackwalkpaths = ['linux', 'minidump_stackwalk']
        elif platform.system() == 'Darwin':
            stackwalkpaths = ['osx', 'minidump_stackwalk']
        else:
            return
        stackwalkbin = os.path.join(os.path.dirname(__file__), 'breakpad', *stackwalkpaths)

        found = False
        minidumpdir = os.path.join(profile_dir, 'minidumps')
        if browser_config['remote'] == True:
            minidumpdir = tempfile.mkdtemp()
            self._ffprocess.testAgent.getDirectory(profile_dir + '/minidumps/', minidumpdir)
        
        for dump in glob.glob(os.path.join(minidumpdir, '*.dmp')):
            utils.noisy("Found crashdump: " + dump)
            if browser_config['symbols_path']:
                nullfd = open(os.devnull, 'w')
                cmd = [stackwalkbin, dump, browser_config['symbols_path']]
                try:
                    subprocess.call(cmd, stderr=nullfd)
                except:
                    raise talosError("error executing: '%s'" % subprocess.list2cmdline(cmd))
                nullfd.close()
            dumpSavePath = os.environ.get('MINIDUMP_SAVE_PATH', None)
            if dumpSavePath:
                shutil.move(dump, dumpSavePath)
                utils.noisy("Saved dump as %s" % os.path.join(dumpSavePath,
                                                              os.path.basename(dump)))
            else:
                os.remove(dump)
            found = True

        if browser_config['remote'] == True:
            self._hostproc.removeDirectory(minidumpdir)
   
        if found:
            if cleanup_result:
                raise talosError("stack found after process termination (" + cleanup_result+ ")")
            else:
                raise talosError("crash during run (stack found)")

    def setupRobocopTests(self, browser_config, profile_dir):
        deviceRoot = self._ffprocess.testAgent.getDeviceRoot()
        fHandle = open("robotium.config", "w")
        fHandle.write("profile=%s\n" % profile_dir)

        remoteLog = deviceRoot + "/" + browser_config['browser_log']
        fHandle.write("logfile=%s\n" % remoteLog)
        fHandle.write("host=http://%s\n" % browser_config['webserver'])
        fHandle.write("rawhost=http://%s\n" % browser_config['webserver'])
        fHandle.close()

        # Note, we are pushing to /sdcard since we have this location hard coded in robocop
        self._ffprocess.testAgent.removeFile("/sdcard/fennec_ids.txt")
        self._ffprocess.testAgent.removeFile("/sdcard/robotium.config")
        self._ffprocess.testAgent.removeFile(remoteLog)
        self._ffprocess.testAgent.pushFile("robotium.config", "/sdcard/robotium.config")
        self._ffprocess.testAgent.pushFile(browser_config['fennecIDs'], "/sdcard/fennec_ids.txt")

    def runTest(self, browser_config, test_config):
        """
            Runs an url based test on the browser as specified in the browser_config dictionary
  
        Args:
            browser_config:  Dictionary of configuration options for the browser (paths, prefs, etc)
            test_config   :  Dictionary of configuration for the given test (url, cycles, counters, etc)

        """
        self.initializeLibraries(browser_config)

        utils.debug("operating with platform_type : " + self.platform_type)
        counters = test_config.get(self.platform_type + 'counters', [])
        resolution = test_config['resolution']
        all_browser_results = []
        all_counter_results = []
        format = ""
        utils.setEnvironmentVars(browser_config['env'])
        utils.setEnvironmentVars({'MOZ_CRASHREPORTER_NO_REPORT': '1'})

        if browser_config['symbols_path']:
            utils.setEnvironmentVars({'MOZ_CRASHREPORTER': '1'})
        else:
            utils.setEnvironmentVars({'MOZ_CRASHREPORTER_DISABLE': '1'})

        utils.setEnvironmentVars({"LD_LIBRARY_PATH" : os.path.dirname(browser_config['browser_path'])})

        profile_dir = None

        try:
            running_processes = self._ffprocess.checkAllProcesses(browser_config['process'], browser_config['child_process'])
            if running_processes:
                msg = " already running before testing started (unclean system)"
                utils.debug(browser_config['process'] + msg)
                running_processes_str = ", ".join([('[%s] %s' % (pid, process_name)) for pid, process_name in running_processes])
                raise talosError("Found processes still running: %s. Please close them before running talos." % running_processes_str)

            # add any provided directories to the installed browser
            for dir in browser_config['dirs']:
                self._ffsetup.InstallInBrowser(browser_config['browser_path'], 
                                            browser_config['dirs'][dir])
  
            # make profile path work cross-platform
            test_config['profile_path'] = os.path.normpath(test_config['profile_path'])
            profile_dir, temp_dir = self.createProfile(test_config['profile_path'], browser_config)
            self.initializeProfile(profile_dir, browser_config)

            if browser_config['fennecIDs']:
                self.setupRobocopTests(browser_config, profile_dir)

            utils.debug("initialized " + browser_config['process'])
            if test_config['shutdown']:
                shutdown = []

            responsiveness = []
            # ignore responsiveness tests on linux until we fix Bug 710296
            if test_config.get('responsiveness') and platform.system() != "Linux":
               utils.setEnvironmentVars({'MOZ_INSTRUMENT_EVENT_LOOP': '1'})
               utils.setEnvironmentVars({'MOZ_INSTRUMENT_EVENT_LOOP_THRESHOLD': '20'})
               utils.setEnvironmentVars({'MOZ_INSTRUMENT_EVENT_LOOP_INTERVAL': '10'})
               responsiveness = []

            for i in range(test_config['cycles']):

                # remove the browser log file
                if os.path.isfile(browser_config['browser_log']):
                    os.chmod(browser_config['browser_log'], 0777)
                    os.remove(browser_config['browser_log'])
                time.sleep(browser_config['browser_wait']) #wait out the browser closing

                # check to see if the previous cycle is still hanging around
                if (i > 0) and self._ffprocess.checkAllProcesses(browser_config['process'], browser_config['child_process']):
                    raise talosError("previous cycle still running")

                # Run the test
                timeout = test_config.get('timeout', 7200) # 2 hours default
                total_time = 0
                url = test_config['url']
                command_line = self._ffprocess.GenerateBrowserCommandLine(browser_config['browser_path'],
                                                                        browser_config['extra_args'],
                                                                        profile_dir,
                                                                        url)

                utils.debug("command line: " + command_line)

                b_log = browser_config['browser_log']
                if self.remote == True:
                    b_log = browser_config['deviceroot'] + '/' + browser_config['browser_log']
                    self._ffprocess.removeFile(b_log)

                b_cmd = self._ffprocess.GenerateBControllerCommandLine(command_line, browser_config, test_config)
                try:
                    process = subprocess.Popen(b_cmd, universal_newlines=True, bufsize=0, env=os.environ)
                except:
                    raise talosError("error executing browser command line '%s': %s" % (subprocess.list2cmdline(cmd), sys.exc_info()[0]))

                #give browser a chance to open
                # this could mean that we are losing the first couple of data points
                # as the tests starts, but if we don't provide
                # some time for the browser to start we have trouble connecting the CounterManager to it
                time.sleep(browser_config['browser_wait'])
                #set up the counters for this test
                if counters:
                    cm = self.cmanager.CounterManager(self._ffprocess, browser_config['process'], counters)
                counter_results = {}
                for counter in counters:
                    counter_results[counter] = []

                startTime = -1
                dumpResult = ""
                #the main test loop, monitors counters and checks for browser output
                while total_time < timeout:
                    # Sleep for [resolution] seconds
                    time.sleep(resolution)
                    total_time += resolution
                    fileData = self._ffprocess.getFile(b_log)
                    if (len(fileData) > 0):
                        utils.noisy(fileData.replace(dumpResult, ''))
                        dumpResult = fileData

                    # Get the output from all the possible counters
                    for count_type in counters:
                        val = cm.getCounterValue(count_type)
                        if (val):
                            counter_results[count_type].append(val)
                    if process.poll() != None: #browser_controller completed, file now full
                        break

                if hasattr(process, 'kill'):
                    # BBB python 2.4 does not have Popen.kill(); see
                    # https://bugzilla.mozilla.org/show_bug.cgi?id=752951#c6
                    try:
                        process.kill()
                    except OSError, e:
                        if (not mozinfo.isWin) and (e.errno != 3):
                            # 3 == No such process in Linux and Mac (errno.h)
                            raise

                if total_time >= timeout:
                    raise talosError("timeout exceeded")

                #stop the counter manager since this test is complete
                if counters:
                    cm.stopMonitor()

                # read the browser output
                browser_log_filename = browser_config['browser_log']
                if not os.path.isfile(browser_log_filename):
                    raise talosError("no output from browser [%s]" % browser_log_filename)
                results_file = open(browser_log_filename)
                results_raw = results_file.read()
                results_file.close()

                # get the results from the browser output
                browser_log_results = results.BrowserLogResults(results_raw, filename=browser_log_filename)
                browser_results = browser_log_results.browser_results
                startTime = browser_log_results.startTime
                endTime = browser_log_results.endTime
                format = browser_log_results.format

                if ("Main_RSS" in counters) or ("Content_RSS" in counters):
                    RSS_REGEX = re.compile('RSS:\s+([a-zA-Z0-9]+):\s+([0-9]+)$')
                    counter_results['Main_RSS'] = []
                    counter_results['Content_RSS'] = []
                    for line in results_raw.split('\n'):
                        rssmatch = RSS_REGEX.search(line)
                        if (rssmatch):
                            (type, value) = (rssmatch.group(1), rssmatch.group(2))
                            if type == 'Main':
                                counter_results['Main_RSS'].append(value)
                            if type == 'Content':
                                counter_results['Content_RSS'].append(value)

                time.sleep(browser_config['browser_wait'])
                #clean up any stray browser processes
                self.cleanupAndCheckForCrashes(browser_config, profile_dir)
                #clean up the bcontroller process
                timer = 0
                while ((process.poll() is None) and timer < browser_config['browser_wait']):
                    time.sleep(1)
                    timer+=1
 
                if test_config['shutdown']:
                    shutdown.append(endTime - startTime)
                # ignore responsiveness tests on linux until we fix Bug 697555
                if test_config.get('responsiveness') and platform.system() != "Linux":
                    responsiveness.extend(browser_log_results.responsiveness())

                all_browser_results.append(browser_results)
                all_counter_results.append(counter_results)

            self.cleanupProfile(temp_dir)
            utils.restoreEnvironmentVars()
            if test_config['shutdown']:
                all_counter_results.append({'shutdown' : shutdown})
            # include tresponsiveness results if taken
            if responsiveness:
                all_counter_results.append({'responsiveness' : responsiveness})
            return (all_browser_results, all_counter_results, format)
        except:
            try:
                if 'cm' in vars():
                    cm.stopMonitor()

                if os.path.isfile(browser_config['browser_log']):
                    results_file = open(browser_config['browser_log'], "r")
                    results_raw = results_file.read()
                    results_file.close()
                    utils.noisy(results_raw)

                if profile_dir:
                    try:
                        self.cleanupAndCheckForCrashes(browser_config, profile_dir)
                    except talosError:
                        pass

                if vars().has_key('temp_dir'):
                    self.cleanupProfile(temp_dir)
            except talosError, te:
                utils.debug("cleanup error: " + te.msg)
            except:
                utils.debug("unknown error during cleanup")
            raise
