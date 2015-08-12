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
import time
import utils
import mozcrash
import talosconfig
import shutil
import mozfile
import logging
from threading import Thread

from talos.utils import TalosError, TalosCrash, TalosRegression
from talos import ffprocess, TalosProcess
from talos.ffsetup import FFSetup


class TTest(object):

    _pids = []
    platform_type = ''

    def __init__(self):
        cmanager, platformtype = self.getPlatformType()
        self.CounterManager = cmanager
        self.platform_type = platformtype

    def getPlatformType(self):
        if platform.system() == "Linux":
            import cmanager_linux
            CounterManager = cmanager_linux.LinuxCounterManager
            platform_type = 'linux_'
        elif platform.system() in ("Windows", "Microsoft"):
            if '5.1' in platform.version():  # winxp
                platform_type = 'win_'
            elif '6.1' in platform.version():  # w7
                platform_type = 'w7_'
            elif '6.2' in platform.version():  # w8
                platform_type = 'w8_'
            else:
                raise TalosError('unsupported windows version')
            import cmanager_win32
            CounterManager = cmanager_win32.WinCounterManager
        elif platform.system() == "Darwin":
            import cmanager_mac
            CounterManager = cmanager_mac.MacCounterManager
            platform_type = 'mac_'
        return CounterManager, platform_type

    def cleanupAndCheckForCrashes(self, browser_config, profile_dir,
                                  test_name):
        """cleanup browser processes and process crashes if found"""

        # cleanup processes
        ffprocess.cleanup_processes(self._pids,
                                    browser_config['browser_wait'])

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
        stackwalkbin = os.path.join(os.path.dirname(__file__), 'breakpad',
                                    *stackwalkpaths)
        assert os.path.exists(stackwalkbin), \
            "minidump_stackwalk binary not found: %s" % stackwalkbin

        # check for minidumps
        minidumpdir = os.path.join(profile_dir, 'minidumps')
        found = mozcrash.check_for_crashes(minidumpdir,
                                           browser_config['symbols_path'],
                                           stackwalk_binary=stackwalkbin,
                                           test_name=test_name)
        mozfile.remove(minidumpdir)

        if found:
            raise TalosCrash("Found crashes after test run, terminating test")

    def testCleanup(self, browser_config, profile_dir, test_config, cm):
        try:
            if os.path.isfile(browser_config['browser_log']):
                with open(browser_config['browser_log'], "r") as results_file:
                    results_raw = results_file.read()
                logging.info(results_raw)

            if profile_dir:
                try:
                    self.cleanupAndCheckForCrashes(browser_config,
                                                   profile_dir,
                                                   test_config['name'])
                except TalosError:
                    # ignore this error since we have already checked for
                    # crashes earlier
                    pass

        except TalosError, te:
            logging.debug("cleanup error: %s", te)
        except Exception:
            logging.debug("unknown error during cleanup: %s"
                          % (traceback.format_exc(),))

    def collectCounters(self):
        # set up the counters for this test
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
            Runs an url based test on the browser as specified in the
            browser_config dictionary

        Args:
            browser_config:  Dictionary of configuration options for the
                             browser (paths, prefs, etc)
            test_config   :  Dictionary of configuration for the given
                             test (url, cycles, counters, etc)

        """

        logging.debug("operating with platform_type : %s", self.platform_type)
        self.counters = test_config.get(self.platform_type + 'counters', [])
        self.resolution = test_config['resolution']
        with FFSetup(browser_config, test_config) as setup:
            return self._runTest(browser_config, test_config, setup)

    def _runTest(self, browser_config, test_config, setup):
        try:

            # add the mainthread_io to the environment variable, as defined
            # in test.py configs
            here = os.path.dirname(os.path.realpath(__file__))
            if test_config['mainthread']:
                mainthread_io = os.path.join(here, "mainthread_io.log")
                setup.env['MOZ_MAIN_THREAD_IO_LOG'] = mainthread_io

            test_config['url'] = utils.interpolate(
                test_config['url'],
                profile=setup.profile_dir,
                firefox=browser_config['browser_path']
            )

            logging.debug("initialized %s", browser_config['process'])

            # setup global (cross-cycle) counters:
            # shutdown, responsiveness
            global_counters = {}
            if browser_config.get('xperf_path'):
                for c in test_config.get('xperf_counters', []):
                    global_counters[c] = []

            if test_config['shutdown']:
                global_counters['shutdown'] = []
            if test_config.get('responsiveness') and \
                    platform.system() != "Linux":
                # ignore responsiveness tests on linux until we fix
                # Bug 710296
                setup.env['MOZ_INSTRUMENT_EVENT_LOOP'] = '1'
                setup.env['MOZ_INSTRUMENT_EVENT_LOOP_THRESHOLD'] = '20'
                setup.env['MOZ_INSTRUMENT_EVENT_LOOP_INTERVAL'] = '10'
                global_counters['responsiveness'] = []

            # instantiate an object to hold test results
            test_results = results.TestResults(
                test_config,
                global_counters
            )

            for i in range(test_config['cycles']):

                # remove the browser log file and error file
                for key in ('browser_log', 'error_filename'):
                    mozfile.remove(browser_config[key])

                # reinstall any file whose stability we need to ensure across
                # the cycles
                if test_config.get('reinstall', ''):
                    for keep in test_config['reinstall']:
                        origin = os.path.join(test_config['profile_path'],
                                              keep)
                        dest = os.path.join(setup.profile_dir, keep)
                        logging.debug("Reinstalling %s on top of %s", origin,
                                      dest)
                        shutil.copy(origin, dest)

                # check to see if the previous cycle is still hanging around
                if (i > 0) and ffprocess.running_processes(self._pids):
                    raise TalosError("previous cycle still running")

                # Run the test
                timeout = test_config.get('timeout', 7200)  # 2 hours default
                if setup.sps_profile:
                    # When profiling, give the browser some extra time
                    # to dump the profile.
                    timeout += 5 * 60

                command_args = utils.GenerateBrowserCommandLine(
                    browser_config["browser_path"],
                    browser_config["extra_args"],
                    setup.profile_dir,
                    test_config['url'],
                    profiling_info=(setup.sps_profile.profiling_info
                                    if setup.sps_profile else None)
                )

                self.counter_results = None
                mainthread_error_count = 0
                if test_config['setup']:
                    # Generate bcontroller.json for xperf
                    talosconfig.generateTalosConfig(command_args,
                                                    browser_config,
                                                    test_config)
                    subprocess.call(
                        ['python'] + test_config['setup'].split(),
                    )

                self.isFinished = False
                mm_httpd = None

                if test_config['name'] == 'media_tests':
                    from startup_test.media import media_manager
                    mm_httpd = media_manager.run_server(
                        os.path.dirname(os.path.realpath(__file__))
                    )

                browser = TalosProcess.TalosProcess(
                    command_args,
                    env=setup.env,
                    logfile=browser_config['browser_log'],
                    suppress_javascript_errors=True,
                    wait_for_quit_timeout=5
                )
                browser.run(timeout=timeout)
                pid = browser.pid
                self._pids.append(pid)

                if self.counters:
                    self.cm = self.CounterManager(
                        browser_config['process'],
                        self.counters
                    )
                    self.counter_results = \
                        dict([(counter, []) for counter in self.counters])
                    cmthread = Thread(target=self.collectCounters)
                    cmthread.setDaemon(True)  # don't hang on quit
                    cmthread.start()

                # todo: ctrl+c doesn't close the browser windows
                try:
                    code = browser.wait()
                except KeyboardInterrupt:
                    browser.kill()
                    raise
                logging.info(
                    "Browser exited with error code: {0}".format(code)
                )
                browser = None
                self.isFinished = True

                if mm_httpd:
                    mm_httpd.stop()

                if test_config['mainthread']:
                    rawlog = os.path.join(here, "mainthread_io.log")
                    if os.path.exists(rawlog):
                        processedlog = \
                            os.path.join(here, 'mainthread_io.json')
                        xre_path = \
                            os.path.dirname(browser_config['browser_path'])
                        mtio_py = os.path.join(here, 'mainthreadio.py')
                        command = ['python', mtio_py, rawlog,
                                   processedlog, xre_path]
                        mtio = subprocess.Popen(command,
                                                env=os.environ.copy(),
                                                stdout=subprocess.PIPE)
                        output, stderr = mtio.communicate()
                        for line in output.split('\n'):
                            if line.strip() == "":
                                continue

                            print line
                            mainthread_error_count += 1
                        mozfile.remove(rawlog)

                if test_config['cleanup']:
                    # HACK: add the pid to support xperf where we require
                    # the pid in post processing
                    talosconfig.generateTalosConfig(command_args,
                                                    browser_config,
                                                    test_config,
                                                    pid=pid)
                    cleanup = TalosProcess.TalosProcess(
                        ['python'] + test_config['cleanup'].split(),
                        env=os.environ.copy()
                    )
                    cleanup.run()
                    cleanup.wait()

                # allow mozprocess to terminate fully.
                # It appears our log file is partial unless we wait
                time.sleep(5)

                # For startup tests, we launch the browser multiple times
                # with the same profile
                for fname in ('sessionstore.js', '.parentlock',
                              'sessionstore.bak'):
                    mozfile.remove(os.path.join(setup.profile_dir, fname))

                # ensure the browser log exists
                browser_log_filename = browser_config['browser_log']
                if not os.path.isfile(browser_log_filename):
                    raise TalosError("no output from browser [%s]"
                                     % browser_log_filename)

                # check for xperf errors
                if os.path.exists(browser_config['error_filename']) or \
                   mainthread_error_count > 0:
                    raise TalosRegression(
                        "Talos has found a regression, if you have questions"
                        " ask for help in irc on #perf"
                    )

                # add the results from the browser output
                try:
                    test_results.add(browser_log_filename,
                                     counter_results=self.counter_results)
                except Exception as e:
                    # Log the exception, but continue. One way to get here
                    # is if the browser hangs, and we'd still like to get
                    # symbolicated profiles in that case.
                    logging.info(e)

                if setup.sps_profile:
                    setup.sps_profile.symbolicate(i)

                # clean up any stray browser processes
                self.cleanupAndCheckForCrashes(browser_config,
                                               setup.profile_dir,
                                               test_config['name'])

            # include global (cross-cycle) counters
            test_results.all_counter_results.extend(
                [{key: value} for key, value in global_counters.items()]
            )
            for c in test_results.all_counter_results:
                for key, value in c.items():
                    print "COUNTER: %s" % key
                    print value

            # return results
            return test_results

        except Exception, e:
            self.counters = vars().get('cm', self.counters)
            self.testCleanup(browser_config, setup.profile_dir, test_config,
                             self.counters)
            raise
