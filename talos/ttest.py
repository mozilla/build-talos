# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""A generic means of running an URL based browser test
   follows the following steps
     - creates a profile
     - tests the profile
     - gets metrics for the current test environment
     - loads the url
     - collects info on any counters while test runs
     - waits for a 'dump' from the browser
"""

import os
import platform
import results
import traceback
import subprocess
import tempfile
import time
import utils
import copy
import mozcrash
import mozdevice
import talosconfig
import shutil
import zipfile
from threading import Thread

from utils import TalosError, TalosCrash, TalosRegression
from ffprocess_linux import LinuxProcess
from ffprocess_win32 import Win32Process
from ffprocess_mac import MacProcess
from ffsetup import FFSetup
import TalosProcess

class TTest(object):

    _ffsetup = None
    _ffprocess = None
    _pids = []
    platform_type = ''

    def __init__(self, remote = False):
        cmanager, platformtype, ffprocess = self.getPlatformType(remote)
        self.CounterManager = cmanager
        self.platform_type = platformtype
        self._ffprocess = ffprocess
        self._hostproc = ffprocess
        self.remote = remote

        self._ffsetup = FFSetup(self._ffprocess)

    def getPlatformType(self, remote):

        _ffprocess = None
        if remote == True:
            platform_type = 'remote_'
            import cmanager
            CounterManager = cmanager.CounterManager
        elif platform.system() == "Linux":
            import cmanager_linux
            CounterManager = cmanager_linux.LinuxCounterManager
            platform_type = 'linux_'
            _ffprocess = LinuxProcess()
        elif platform.system() in ("Windows", "Microsoft"):
            if '5.1' in platform.version(): #winxp
                platform_type = 'win_'
            elif '6.1' in platform.version(): #w7
                platform_type = 'w7_'
            elif '6.2' in platform.version(): #w8
                platform_type = 'w8_'
            else:
                raise TalosError('unsupported windows version')
            import cmanager_win32
            CounterManager = cmanager_win32.WinCounterManager
            _ffprocess = Win32Process()
        elif platform.system() == "Darwin":
            import cmanager_mac
            CounterManager = cmanager_mac.MacCounterManager
            platform_type = 'mac_'
            _ffprocess = MacProcess()
        return CounterManager, platform_type, _ffprocess

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

    def createProfile(self, profile_path, preferences, extensions, webserver):
        # Create the new profile
        temp_dir, profile_dir = self._ffsetup.CreateTempProfileDir(profile_path,
                                                     preferences,
                                                     extensions,
                                                     webserver)
        utils.debug("created profile")
        return profile_dir, temp_dir

    def initializeProfile(self, profile_dir, browser_config):
        res, pid = self._ffsetup.InitializeNewProfile(profile_dir, browser_config)
        if pid:
            self._pids.append(pid)
        if not res:
            raise TalosError("failed to initialize browser")
        processes = self._ffprocess.checkProcesses(self._pids)
        if processes:
            raise TalosError("browser failed to close after being initialized")

    def cleanupProfile(self, dir):
        # Delete the temp profile directory  Make it writeable first,
        # because every once in a while browser seems to drop a read-only
        # file into it.
        self._hostproc.removeDirectory(dir)

    def cleanupAndCheckForCrashes(self, browser_config, profile_dir, test_name):
        """cleanup browser processes and process crashes if found"""

        # cleanup processes
        self._ffprocess.cleanupProcesses(self._pids, browser_config['browser_wait'])

        # find stackwalk binary
        if platform.system() in ('Windows', 'Microsoft'):
            stackwalkpaths = ['win32', 'minidump_stackwalk.exe']
        elif platform.system() == 'Linux':
            # are we 64 bit?
            if '64' in platform.architecture()[0]:
                stackwalkpaths = ['linux64', 'minidump_stackwalk']
            else:
                stackwalkpaths = ['linux', 'minidump_stackwalk']
        elif platform.system() == 'Darwin':
            stackwalkpaths = ['osx', 'minidump_stackwalk']
        else:
            # no minidump_stackwalk available for your platform
            return
        stackwalkbin = os.path.join(os.path.dirname(__file__), 'breakpad', *stackwalkpaths)
        assert os.path.exists(stackwalkbin), "minidump_stackwalk binary not found: %s" % stackwalkbin

        if browser_config['remote'] is True:
            # favour using Java exceptions in the logcat over minidumps
            if os.path.exists('logcat.log'):
                with open('logcat.log') as f:
                    logcat = f.read().split('\r')
                found = mozcrash.check_for_java_exception(logcat)

            remoteminidumpdir = profile_dir + '/minidumps/'
            if not found:
                # check for minidumps
                minidumpdir = tempfile.mkdtemp()
                try:
                    if self._ffprocess.testAgent.dirExists(remoteminidumpdir):
                        self._ffprocess.testAgent.getDirectory(remoteminidumpdir, minidumpdir)
                except mozdevice.DMError:
                    print "Remote Device Error: Error getting crash minidumps from device"
                    raise
                found = mozcrash.check_for_crashes(minidumpdir,
                                                   browser_config['symbols_path'],
                                                   stackwalk_binary=stackwalkbin,
                                                   test_name=test_name)
                self._hostproc.removeDirectory(minidumpdir)

            # cleanup dumps on remote
            self._ffprocess.testAgent.removeDir(remoteminidumpdir)
        else:
            # check for minidumps
            minidumpdir = os.path.join(profile_dir, 'minidumps')
            found = mozcrash.check_for_crashes(minidumpdir,
                                               browser_config['symbols_path'],
                                               stackwalk_binary=stackwalkbin,
                                               test_name=test_name)
            self._hostproc.removeDirectory(minidumpdir)

        if found:
            raise TalosCrash("Found crashes after test run, terminating test")

    def setupRobocopTests(self, browser_config, profile_dir):
        try:
            deviceRoot = self._ffprocess.testAgent.getDeviceRoot()
            fHandle = open("robotium.config", "w")
            fHandle.write("profile=%s\n" % profile_dir)

            remoteLog = deviceRoot + "/" + browser_config['browser_log']
            fHandle.write("logfile=%s\n" % remoteLog)
            fHandle.write("host=http://%s\n" % browser_config['webserver'])
            fHandle.write("rawhost=http://%s\n" % browser_config['webserver'])
            envstr = ""
            delim = ""
            # This is not foolproof and the ideal solution would be to have one env/line instead of a single string
            for key, value in browser_config.get('env', {}).items():
                try:
                    value.index(',')
                    print "Error: Found an ',' in our value, unable to process value."
                except ValueError:
                    envstr += "%s%s=%s" % (delim, key, value)
                    delim = ","

            fHandle.write("envvars=%s\n" % envstr)
            fHandle.close()

            self._ffprocess.testAgent.removeFile(os.path.join(deviceRoot, "fennec_ids.txt"))
            self._ffprocess.testAgent.removeFile(os.path.join(deviceRoot, "robotium.config"))
            self._ffprocess.testAgent.removeFile(remoteLog)
            self._ffprocess.testAgent.pushFile("robotium.config", os.path.join(deviceRoot, "robotium.config"))
            self._ffprocess.testAgent.pushFile(browser_config['fennecIDs'], os.path.join(deviceRoot, "fennec_ids.txt"))
        except mozdevice.DMError:
            print "Remote Device Error: Error copying files for robocop setup"
            raise


    def testCleanup(self, browser_config, profile_dir, test_config, cm, temp_dir):
        try:
            if os.path.isfile(browser_config['browser_log']):
                results_file = open(browser_config['browser_log'], "r")
                results_raw = results_file.read()
                results_file.close()
                utils.info(results_raw)

            if profile_dir:
                try:
                    self.cleanupAndCheckForCrashes(browser_config, profile_dir, test_config['name'])
                except TalosError:
                    # ignore this error since we have already checked for crashes earlier
                    pass

            if temp_dir:
                self.cleanupProfile(temp_dir)
        except TalosError, te:
            utils.debug("cleanup error: %s", te)
        except Exception:
            utils.debug("unknown error during cleanup: %s" % (traceback.format_exc(),))


    def collectCounters(self):
        #set up the counters for this test
        if self.counters:
            while not self.isFinished:
                time.sleep(self.resolution)
                # Get the output from all the possible counters
                for count_type in self.counters:
                    if not self.cm:
                        continue
                    val = self.cm.getCounterValue(count_type)
                    if val and self.counter_results:
                        self.counter_results[count_type].append(val)

    def runTest(self, browser_config, test_config):
        """
            Runs an url based test on the browser as specified in the browser_config dictionary

        Args:
            browser_config:  Dictionary of configuration options for the browser (paths, prefs, etc)
            test_config   :  Dictionary of configuration for the given test (url, cycles, counters, etc)

        """
        self.initializeLibraries(browser_config)

        utils.debug("operating with platform_type : %s", self.platform_type)
        self.counters = test_config.get(self.platform_type + 'counters', [])
        self.resolution = test_config['resolution']
        utils.setEnvironmentVars(browser_config['env'])
        utils.setEnvironmentVars({'MOZ_CRASHREPORTER_NO_REPORT': '1'})
        # for winxp e10s logging: https://bugzilla.mozilla.org/show_bug.cgi?id=1037445
        utils.setEnvironmentVars({'MOZ_WIN_INHERIT_STD_HANDLES_PRE_VISTA': '1'})
        if browser_config['symbols_path']:
            utils.setEnvironmentVars({'MOZ_CRASHREPORTER': '1'})
        else:
            utils.setEnvironmentVars({'MOZ_CRASHREPORTER_DISABLE': '1'})

        # Crash on non-local network connections.
        # Not enabled for Android tprovider due to yet to be diagnosed connections
        # to safebrowsing.google.com.
        if test_config['name'] != 'tprovider':
            utils.setEnvironmentVars({'MOZ_DISABLE_NONLOCAL_CONNECTIONS': '1'})

        utils.setEnvironmentVars({"LD_LIBRARY_PATH" : os.path.dirname(browser_config['browser_path'])})

        profile_dir = None
        temp_dir = None

        try:
            # add any provided directories to the installed browser
            for dir in browser_config['dirs']:
                self._ffsetup.InstallInBrowser(browser_config['browser_path'],
                                            browser_config['dirs'][dir])

            # make profile path work cross-platform
            test_config['profile_path'] = os.path.normpath(test_config['profile_path'])

            # add the mainthread_io to the environment variable, as defined in test.py configs
            here = os.path.dirname(os.path.realpath(__file__))
            if test_config['mainthread']:
                mainthread_io = os.path.join(here, "mainthread_io.log")
                utils.setEnvironmentVars({'MOZ_MAIN_THREAD_IO_LOG': mainthread_io})

            preferences = copy.deepcopy(browser_config['preferences'])
            if 'preferences' in test_config and test_config['preferences']:
                testPrefs = dict([(i, utils.parsePref(j)) for i, j in test_config['preferences'].items()])
                preferences.update(testPrefs)

            extensions = copy.deepcopy(browser_config['extensions'])
            if 'extensions' in test_config and test_config['extensions']:
                extensions.append(test_config['extensions'])

            profile_dir, temp_dir = self.createProfile(test_config['profile_path'],
                                                       preferences,
                                                       extensions,
                                                       browser_config['webserver'])
            self.initializeProfile(profile_dir, browser_config)
            test_config['url'] = utils.interpolatePath(test_config['url'], profile_dir=profile_dir, firefox_path=browser_config['browser_path'])

            if browser_config['fennecIDs']:
                # This pushes environment variables to the device, be careful of placement
                self.setupRobocopTests(browser_config, profile_dir)

            upload_dir = os.environ.get('MOZ_UPLOAD_DIR', None)
            sps_profile = upload_dir and test_config.get('sps_profile', False) and not browser_config['remote']
            sps_profile_dir = None
            profile_arcname = None
            profiling_info = None

            additional_env_vars = {}

            if sps_profile:
                # Create a temporary directory into which the tests can put their profiles.
                # These files will be assembled into one big zip file later on, which is put
                # into the MOZ_UPLOAD_DIR.
                sps_profile_dir = tempfile.mkdtemp();

                sps_profile_interval = test_config.get('sps_profile_interval', 1)
                sps_profile_entries = test_config.get('sps_profile_entries', 1000000)
                sps_profile_threads = 'GeckoMain,Compositor'

                # Make sure no archive already exists in the location where we plan to output
                # our profiler archive
                profile_arcname = os.path.join(upload_dir, "profile_{0}.sps.zip".format(test_config['name']))
                try:
                    utils.info("Clearing archive {0}".format(profile_arcname))
                    os.remove(profile_arcname)
                except OSError:
                    pass

                profiling_info = {
                    "sps_profile_interval": sps_profile_interval,
                    "sps_profile_entries": sps_profile_entries,
                    "sps_profile_dir": sps_profile_dir,
                    "sps_profile_threads": sps_profile_threads
                }

                if test_config.get('sps_profile_startup', False):
                    # Set environment variables which will cause profiling to
                    # start as early as possible. These are consumed by Gecko
                    # itself, not by Talos JS code.
                    additional_env_vars = {
                        'MOZ_PROFILER_STARTUP': '1',
                        'MOZ_PROFILER_INTERVAL': str(sps_profile_interval),
                        'MOZ_PROFILER_ENTRIES': str(sps_profile_entries),
                        "MOZ_PROFILER_THREADS": str(sps_profile_threads)
                    }

            utils.debug("initialized %s", browser_config['process'])

            # setup global (cross-cycle) counters:
            # shutdown, responsiveness
            global_counters = {}
            if browser_config.get('xperf_path'):
                for c in test_config.get('xperf_counters', []):
                    global_counters[c] = []

            if test_config['shutdown']:
                global_counters['shutdown'] = []
            if test_config.get('responsiveness') and platform.system() != "Linux":
                # ignore responsiveness tests on linux until we fix Bug 710296
                utils.setEnvironmentVars({'MOZ_INSTRUMENT_EVENT_LOOP': '1'})
                utils.setEnvironmentVars({'MOZ_INSTRUMENT_EVENT_LOOP_THRESHOLD': '20'})
                utils.setEnvironmentVars({'MOZ_INSTRUMENT_EVENT_LOOP_INTERVAL': '10'})
                global_counters['responsiveness'] = []

            # instantiate an object to hold test results
            test_results = results.TestResults(test_config, global_counters, extensions=self._ffsetup.extensions)

            for i in range(test_config['cycles']):

                # remove the browser log file
                if os.path.isfile(browser_config['browser_log']):
                    os.chmod(browser_config['browser_log'], 0777)
                    os.remove(browser_config['browser_log'])

                # remove the error file if it exists
                if os.path.exists(browser_config['error_filename']):
                    os.chmod(browser_config['error_filename'], 0777)
                    os.remove(browser_config['error_filename'])

                # reinstall any file whose stability we need to ensure across
                # the cycles
                if test_config.get('reinstall', ''):
                    for keep in test_config['reinstall']:
                        origin = os.path.join(test_config['profile_path'], keep)
                        dest = os.path.join(profile_dir, keep)
                        utils.debug("Reinstalling %s on top of %s", origin, dest)
                        shutil.copy(origin, dest)

                # check to see if the previous cycle is still hanging around
                if (i > 0) and self._ffprocess.checkProcesses(self._pids):
                    raise TalosError("previous cycle still running")

                # Run the test
                timeout = test_config.get('timeout', 7200) # 2 hours default

                command_args = utils.GenerateBrowserCommandLine(browser_config["browser_path"],
                                                                browser_config["extra_args"],
                                                                browser_config["deviceroot"],
                                                                profile_dir,
                                                                test_config['url'],
                                                                profiling_info=profiling_info)

                self.counter_results = None
                mainthread_error_count = 0
                if not browser_config['remote']:
                    if test_config['setup']:
                        # Generate bcontroller.yml for xperf
                        talosconfig.generateTalosConfig(command_args, browser_config, test_config)
                        setup = subprocess.Popen(['python'] + test_config['setup'].split(), env=os.environ.copy(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        stdout, stderr = setup.communicate()
                        print "-----------------------------------------------------------------------------"
                        print "output of setup command:"
                        print stdout
                        print stderr
                        print "end of setup command output"
                        print "-----------------------------------------------------------------------------"

                    self.isFinished = False
                    mm_httpd = None

                    if test_config['name'] == 'media_tests':
                        from startup_test.media import media_manager
                        mm_httpd = media_manager.run_server(os.path.dirname(os.path.realpath(__file__)))

                    browser = TalosProcess.TalosProcess(command_args,
                                                        env=dict(os.environ.items() + additional_env_vars.items()),
                                                        logfile=browser_config['browser_log'],
                                                        supress_javascript_errors=True,
                                                        wait_for_quit_timeout=5)
                    browser.run(timeout=timeout)
                    pid = browser.pid
                    self._pids.append(pid)

                    if self.counters:
                        self.cm = self.CounterManager(browser_config['process'], self.counters)
                        self.counter_results = dict([(counter, []) for counter in self.counters])
                        cmthread = Thread(target=self.collectCounters)
                        cmthread.setDaemon(True) # don't hang on quit
                        cmthread.start()

                    # todo: ctrl+c doesn't close the browser windows
                    code = browser.wait()
                    utils.info("Browser exited with error code: {0}".format(code))
                    browser = None
                    self.isFinished = True

                    if mm_httpd:
                        mm_httpd.stop()

                    if test_config['mainthread']:
                        rawlog = os.path.join(here, "mainthread_io.log")
                        if os.path.exists(rawlog):
                            processedlog = os.path.join(here, 'mainthread_io.json')
                            xre_path = os.path.dirname(browser_config['browser_path'])
                            mtio_py = os.path.join(here, 'mainthreadio.py')
                            command = ['python', mtio_py, rawlog, processedlog, xre_path]
                            mtio = subprocess.Popen(command, env=os.environ.copy(), stdout=subprocess.PIPE)
                            output, stderr = mtio.communicate()
                            for line in output.split('\n'):
                                if line.strip() == "":
                                    continue

                                print line
                                mainthread_error_count += 1
                            os.remove(rawlog)

                    if test_config['cleanup']:
                        #HACK: add the pid to support xperf where we require the pid in post processing
                        talosconfig.generateTalosConfig(command_args, browser_config, test_config, pid=pid)
                        cleanup = TalosProcess.TalosProcess(['python'] + test_config['cleanup'].split(), env=os.environ.copy())
                        cleanup.run()
                        cleanup.wait()

                    # allow mozprocess to terminate fully.  It appears our log file is partial unless we wait
                    time.sleep(5)
                else:
                    self._ffprocess.runProgram(browser_config, command_args, timeout=timeout)

                # For startup tests, we launch the browser multiple times with the same profile
                try:
                    os.remove(os.path.join(profile_dir, 'sessionstore.js'))
                except:
                    pass
                try:
                    os.remove(os.path.join(profile_dir, '.parentlock'))
                except:
                    pass
                try:
                    os.remove(os.path.join(profile_dir, 'sessionstore.bak'))
                except:
                    pass

                # ensure the browser log exists
                browser_log_filename = browser_config['browser_log']
                if not os.path.isfile(browser_log_filename):
                    raise TalosError("no output from browser [%s]" % browser_log_filename)

                # check for xperf errors
                if os.path.exists(browser_config['error_filename']) or \
                   mainthread_error_count > 0:
                    raise TalosRegression("Talos has found a regression, if you have questions ask for help in irc on #perf")

                # add the results from the browser output
                test_results.add(browser_log_filename, counter_results=self.counter_results)

                if sps_profile:
                    try:
                        mode = zipfile.ZIP_DEFLATED
                    except:
                        mode = zipfile.ZIP_STORED
                    with zipfile.ZipFile(profile_arcname, 'a', mode) as arc:
                        # Collect all individual profiles that the test has put into sps_profile_dir.
                        for profile_filename in os.listdir(sps_profile_dir):
                            testname = profile_filename
                            if testname.endswith(".sps"):
                                testname = testname[0:-4]
                            profile_path = os.path.join(sps_profile_dir, profile_filename)

                            # Our zip will contain one directory per subtest, and each subtest
                            # directory will contain one or more cycle_i.sps files.
                            # For example, with test_config['name'] == 'tscrollx',
                            #  profile_filename == 'iframe.svg.sps', i == 0, we'll get
                            #  path_in_zip == 'profile_tscrollx/iframe.svg/cycle_0.sps'.
                            cycle_name = "cycle_{0}.sps".format(i)
                            path_in_zip = os.path.join("profile_{0}".format(test_config['name']), testname, cycle_name)
                            utils.info("Adding profile {0} to archive {1}".format(path_in_zip, profile_arcname))
                            try:
                                arc.write(profile_path, path_in_zip)
                            except Exception as e:
                                utils.info(e)
                                utils.info("Failed to copy profile {0} as {1} to archive {2}".format(profile_path, path_in_zip, profile_arcname))

                #clean up any stray browser processes
                self.cleanupAndCheckForCrashes(browser_config, profile_dir, test_config['name'])
                #clean up the bcontroller process

            # cleanup
            self.cleanupProfile(temp_dir)
            utils.restoreEnvironmentVars()
            if sps_profile:
                shutil.rmtree(sps_profile_dir)

            # include global (cross-cycle) counters
            test_results.all_counter_results.extend([{key: value} for key, value in global_counters.items()])

            # return results
            return test_results

        except Exception, e:
            self.counters = vars().get('cm', self.counters)
            self.testCleanup(browser_config, profile_dir, test_config, self.counters, temp_dir)
            raise
