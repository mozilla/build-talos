#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

"""
performance configuration for Talos
"""

import filter
import os
import sys
import copy
import test
import utils
from configuration import Configuration
from configuration import YAML
from datetime import datetime

try:
    import mozdevice
except:
    # mozdevice is known not to import correctly with python 2.4, which we
    # still support
    mozdevice = None

__all__ = ['ConfigurationError', 'PerfConfigurator', 'main']

class ConfigurationError(Exception):
    """error when parsing Talos configuration"""


class PerfConfigurator(Configuration):
    options = [
        ('browser_path', {'help': "path to executable we are testing",
                          'flags': ['-e', '--executablePath']
                          }),
        ('title', {'help': 'Title of the test run',
                   'default': 'qm-pxp01',
                   'flags': ['-t', '--title']}),
        ('branch_name', {'help': 'Name of the branch we are testing on',
                         'default': '',
                         'flags': ['--branchName']}),
        ('browser_wait', {'help': 'Amount of time allowed for the browser to cleanly close',
                          'default': 5,
                          'flags': ['-w', '--browserWait']}),
        ('resultsServer', {'help': "Address of the results server [DEPRECATED: use --resultsURL]"}),
        ('resultsLink', {'help': 'Link to the results from this test run [DEPRECATED: use --resultsURL]',
                         'flags': ['-l', '--resultsLink']}),
        ('results_urls', {'help': 'URL of graphserver or file:// url for local output',
                         'flags': ['--results_url'],
                         'type': list}),
        ('datazilla_urls', {'help': 'URL of datazilla server of file:// url for local output',
                            'flags': ['--datazilla-url'],
                            'type': list}),
        ('authfile', {'help': """File of the form
http://hg.mozilla.org/build/buildbot-configs/file/default/mozilla/passwords.py.template
for datazilla auth.  Should have keys 'oauthSecret' and 'oauthKey'"""}),

        # XXX activeTests should really use a list-thingy but can't because of
        # the one-off ':' separation :/
        ('activeTests', {'help': "List of tests to run, separated by ':' (ex. ts:tp4:tsvg)",
                         'flags': ['-a', '--activeTests']}),

        ('noChrome',  {'help': 'do not run tests as chrome',
                       'type': bool}),
        ('rss', {'help': "Collect RSS counters from pageloader instead of the operating system",
                 'type': bool}),
        ('tpmozafterpaint', {'help': 'wait for MozAfterPaint event before recording the time',
                             'type': bool,
                             'flags': ['--mozAfterPaint']}),

        ('extensions', {'help': 'Extension to install while running',
                        'default': ['${talos}/pageloader'],
                        'flags': ['--extension']}),
        ('fast', {'help': 'Run tp tests as tp_fast',
                  'type': bool}),
        ('symbols_path', {'help': 'Path to the symbols for the build we are testing',
                          'flags': ['--symbolsPath']}),
        ('xperf_path', {'help': 'Path to windows performance tool xperf.exe'}),
        ('test_timeout', {'help': 'Time to wait for the browser to output to the log file',
                          'default': 1200}),
        ('browser_log', {'help': 'Local log file to store the output from the browser in',
                         'default': 'browser_output.txt',
                         'flags': ['--logFile']}),
        ('error_filename', {'help': 'Filename to store the errors found during the test.  Currently used for xperf only.',
                         'default': os.path.abspath('browser_failures.txt'),
                         'flags': ['--errorFile']}),
        ('shutdown', {'help': 'Record time browser takes to shutdown after testing',
                      'type': bool,
                      'flags': ['--noShutdown']}),
        ('extraPrefs', {'help': 'defines an extra user preference',
                        # TODO: metavar = "PREF=VALUE"
                        'default': {},
                        'flags': ['--setPref']}),
        ('webserver', {'help': 'address of the webserver hosting the talos files',
                       'flags': ['--webServer']}),
        ('develop', {'help': "useful for running tests on a developer machine.  Creates a local webserver and doesn't upload to the graph servers.",
                     'default': False}),
        ('responsiveness', {'help': 'turn on responsiveness collection',
                            'type': bool}),
        ('ignore_first', {'help': """Alternative median calculation from pageloader data.
Use the raw values and discard the first page load instead of
the highest value.
[DEPRECATED: use `--filter ignore_first --filter median`]""",
                          'default': False,
                          'flags': ['--ignoreFirst']}),
        ('filters', {'help': 'filters to apply to the data from talos.filters [DEFAULT: ignore_max, median]',
                     'type': list,
                     'flags': ['--filter']}),
        ('cycles', {'help': 'number of browser cycles to run',
                    'type': int}),
        ('tpmanifest', {'help': 'manifest file to test'}),
        ('tpcycles', {'help': 'number of pageloader cycles to run',
                      'type': int}),
        ('tppagecycles', {'help': 'number of pageloader cycles to run for each page in the manifest',
                          'type': int}),
        ('tpdelay', {'help': 'length of the pageloader delay',
                     'type': int}),
        ('sourcestamp',  {'help': 'Specify the hg revision or sourcestamp for the changeset we are testing.  This will use the value found in application.ini if it is not specified.'}),
        ('repository',  {'help': 'Specify the url for the repository we are testing.  This will use the value found in application.ini if it is not specified.'}),

        ### arguments without command line options
        ('extra_args', {'help': 'arguments to pass to browser',
                        'default': '',
                        'flags': []}),
        ('bcontroller_config', {'help': 'path to YAML input for bcontroller',
                                'default': '${talos}/bcontroller.yml',
                                'flags': []}),
        ('buildid', {'default': 'testbuildid',
                     'flags': []}),
        ('init_url', {'default': 'getInfo.html',
                      'flags': []}),
        ('dirs', {'default': {},
                  'flags': []}),
        ('env', {'default': {'NO_EM_RESTART': '1'},
                 'flags': []}),
        ('basetest', {'help': 'base data for all tests',
                      'default': {'cycles': 1,
                                  'profile_path': '${talos}/base_profile',
                                  'responsiveness': False,
                                  'resolution': 1,
                                  'rss': False,
                                  'shutdown': False,
                                  'timeout': 3600,
                                  'tpchrome': True,
                                  'tpcycles': 10,
                                  'tpmozafterpaint': False,
                                  'tpnoisy': True,
                                  'tppagecycles': 1,
                                  'tploadaboutblank': False,
                                  'tprender': False,
                                  'win_counters': [],
                                  'w7_counters': [],
                                  'linux_counters': [],
                                  'mac_counters': [],
                                  'xperf_counters': [],
                                  'setup': None,
                                  'cleanup': None
                                  },
                      'flags': []}),
        ('test_overrides', {'help': 'test overrides from .config file',
                            'type': dict,
                            'flags': []}),
        ('test_name_extension', {'help': 'test name extension',
                                 'flags': []}),
        ('process', {'help': 'process name',
                     'flags': []}),
        ('tests', {'help': 'tests to run',
                   'flags': []}),
        ('remote', {'flags': []}),

        ### remote-specific options
        ('deviceip', {'help': 'Device IP (when using SUTAgent)',
                      'flags': ['-r', '--remoteDevice']}),
        ('deviceport', {'help': "SUTAgent port (defaults to 20701, specify -1 to use ADB)",
                        'default': 20701,
                        'flags': ['-p', '--remotePort']}),
        ('deviceroot', {'help': 'path on the device that will hold files and the profile',
                        'flags': ['--deviceRoot']}),
        ('fennecIDs', {'help': 'Location of the fennec_ids.txt map file, used for robocop based tests',
                       'flags': ['--fennecIDs']}),
        ]

    # remote-specific defaults
    remote_defaults = {'basetest': {
            'timeout': 3600,
            'profile_path': '${talos}/mobile_profile',
            'remote_counters': [],
            'tpcycles': 3,
            'tpdelay': 1000
            },
                       'browser_wait': 20,
                       'test_timeout': 3600,
                       'env': {'MOZ_CRASHREPORTER_NO_REPORT': '1',
                               'MOZ_CRASHREPORTER_SHUTDOWN': '1'},
                       'dirs': {},
                       'process': 'fennec',
                       'title': 'mobile',
                       'test_overrides': {'ts':
                                              {'cycles': 20,
                                               'timeout': 150},
                                          'ts_paint':
                                              {'cycles': 20},
                                          'ts_places_generated_max':
                                              {'cycles': 10,
                                               'timeout': 150},
                                          'ts_places_generated_min':
                                              {'cycles': 10,
                                               'timeout': 150},
                                          'ts_places_generated_med':
                                              {'cycles': 10,
                                               'timeout': 150},
                                          'tdhtml':
                                              {'tpcycles': 3},
                                          'tsvg':
                                              {'tpcycles': 3},
                                          'tsspider':
                                              {'tpcycles': 3}
                                          }
                       }

    # default preferences to run with
    # these are updated with --extraPrefs from the commandline
    # for extension scopes, see
    # see https://developer.mozilla.org/en/Installing_extensions
    preferences = {
        'app.update.enabled': False,
        'browser.bookmarks.max_backups': 0,
        'browser.cache.disk.smart_size.enabled': False,
        'browser.cache.disk.smart_size.first_run': False,
        'browser.chrome.dynamictoolbar': False,
        'browser.dom.window.dump.enabled': True,
        'browser.EULA.override': True,
        'browser.link.open_newwindow': 2,
        'browser.shell.checkDefaultBrowser': False,
        'browser.warnOnQuit': False,
        'browser.display.overlaynavbuttons': False, # metrofx specific
        'dom.allow_scripts_to_close_windows': True,
        'dom.disable_open_during_load': False,
        'dom.disable_window_flip': True,
        'dom.disable_window_move_resize': True,
        'dom.max_chrome_script_run_time': 0,
        'dom.max_script_run_time': 0,
        'extensions.autoDisableScopes': 10,
        'extensions.checkCompatibility': False,
        'extensions.enabledScopes': 5,
        'extensions.update.notifyUser': False,
        'hangmonitor.timeout': 0,
        'network.proxy.http': 'localhost',
        'network.proxy.http_port': 80,
        'network.proxy.type': 1,
        'security.enable_java': False,
        'security.fileuri.strict_origin_policy': False,
        'toolkit.telemetry.prompted': 999,
        'toolkit.telemetry.notifiedOptOut': 999,
        'dom.send_after_paint_to_content': True,
        'security.turn_off_all_security_so_that_viruses_can_take_over_this_computer': True,
        'browser.safebrowsing.gethashURL': 'http://127.0.0.1/safebrowsing-dummy/gethash',
        'browser.safebrowsing.keyURL': 'http://127.0.0.1/safebrowsing-dummy/newkey',
        'browser.safebrowsing.updateURL': 'http://127.0.0.1/safebrowsing-dummy/update',
        'extensions.update.url': 'http://127.0.0.1/extensions-dummy/updateURL',
        'extensions.update.background.url': 'http://127.0.0.1/extensions-dummy/updateBackgroundURL',
        'extensions.blocklist.enabled': False,
        'extensions.blocklist.url': 'http://127.0.0.1/extensions-dummy/blocklistURL',
        'extensions.hotfix.url': 'http://127.0.0.1/extensions-dummy/hotfixURL',
        'extensions.update.enabled': False,
        'extensions.webservice.discoverURL': 'http://127.0.0.1/extensions-dummy/discoveryURL',
        'extensions.getAddons.maxResults': 0,
        'extensions.getAddons.get.url': 'http://127.0.0.1/extensions-dummy/repositoryGetURL',
        'extensions.getAddons.getWithPerformance.url': 'http://127.0.0.1/extensions-dummy/repositoryGetWithPerformanceURL',
        'extensions.getAddons.search.browseURL': 'http://127.0.0.1/extensions-dummy/repositoryBrowseURL',
        'extensions.getAddons.search.url': 'http://127.0.0.1/extensions-dummy/repositorySearchURL',
        'plugins.update.url': 'http://127.0.0.1/plugins-dummy/updateCheckURL'
    }

    # keys to generated self.config that are global overrides to tests
    global_overrides = ['cycles',
                        'responsiveness',
                        'rss',
                        'shutdown',
                        'tpcycles',
                        'tpdelay',
                        'tppagecycles',
                        'tpmanifest',
                        'tpmozafterpaint'
                        ]

    # default filters
    filters = ['ignore_max', 'median']

    # counters turned on by CLI options
    counters = {'rss': ['Main_RSS']}

    # config items to extend vs overwrite
    extend = set(['basetest', 'extraPrefs'])

    # whether to dump by default
    _dump = True

    ### methods overridden from configuration.py

    def __init__(self, **kwargs):

        self.remote = False

        # add preferences to the configuration
        # TODO: do at class level
        self.options.append(('preferences', {'help': 'browser preferences',
                                             'default': self.preferences,
                                             'flags': []}))

        # set arguments to dump to a configuration file
        kwargs.setdefault('dump', ['-o', '--output'])

        # set usage argument
        kwargs.setdefault('usage', '%prog [options] manifest.yml [manifest.yml] [...]')

        # TODO: something about deviceroot:
        # http://hg.mozilla.org/build/talos/file/c702ff8892be/talos/PerfConfigurator.py#l44

        # call parent constructor
        Configuration.__init__(self, **kwargs)

    def optparse_options(self, parser):
        Configuration.optparse_options(self, parser)

        # PerfConfigurator specific options
        # to use used only in parse_args
        parser.add_option('-v', '--verbose', dest='verbose',
                          action='store_true', default=False,
                          help="Dump configuration to stdout")
        parser.add_option('--print-tests', dest='print_tests',
                          action='store_true', default=False,
                          help="Print the resulting tests configuration to stdout (or print available tests if --activeTests not specified)")

    def __call__(self, *args):

        # determine if remote
        self.remote = self.is_remote(args)

        # if remote ensure mozdevice package is available
        if self.remote and (mozdevice is None):
            raise ConfigurationError("Configuration is for a remote device but mozdevice is not available")

        # add remote-specific defaults before parsing
        if self.remote:
            for key, value in self.remote_defaults.items():
                default = self.option_dict[key].get('default')
                if isinstance(default, dict):
                    default.update(value)
                else:
                    self.option_dict[key]['default'] = value

        return Configuration.__call__(self, *args)

    def validate(self):
        """validate and finalize configuration"""

        self.config['remote'] = self.remote

        if self.remote:
            # setup remote
            deviceip = self.config.get('deviceip')
            deviceport = self.config['deviceport']
            if deviceip or deviceport == -1:
                self._setupRemote(deviceip, deviceport)

            # fix webserver for --develop mode
            if self.config.get('develop'):
                webserver = self.config.get('webserver')
                if (not webserver) or (webserver == 'localhost'):
                    self.config['webserver'] = utils.getLanIp()

            # webServer can be used without remoteDevice, but is required when using remoteDevice
            if self.config.get('deviceip') or self.config.get('deviceroot'):
                if self.config.get('webserver', 'localhost') == 'localhost' or not self.config.get('deviceip'):
                    raise ConfigurationError("When running Talos on a remote device, you need to provide a webServer and optionally a remotePort")

            fennecIDs = self.config.get('fennecIDs')
            if fennecIDs and not os.path.exists(fennecIDs):
                raise ConfigurationError("Unable to find fennce IDs file, please ensure this file exists: %s" % fennecIDs)

            # robocop based tests (which use fennecIDs) do not use or need the pageloader extension
            if fennecIDs:
                self.config['extensions'] = []

        # generic configuration validation
        Configuration.validate(self)

        # ensure the browser_path is specified
        msg = "Please specify --executablePath"
        if not 'print_tests' in self.parsed and not self.config.get('browser_path'):
            self.error(msg)

        # BBB: (resultsServer, resultsLink) -> results_url
        resultsServer = self.config.pop('resultsServer', None)
        resultsLink = self.config.pop('resultsLink', None)
        if resultsServer and resultsLink:
            if self.config.get('results_urls'):
                raise Configuration("Can't user resultsServer/resultsLink and results_url: use results_url instead")
            self.config['results_urls'] = ['http://%s%s' % (resultsServer, resultsLink)]

        # BBB: remove doubly-quoted xperf values from command line
        # (needed for buildbot)
        # https://bugzilla.mozilla.org/show_bug.cgi?id=704654#c43
        xperf_path = self.config.get('xperf_path', '')
        if 'xperf_path' in self.parsed and len(xperf_path) > 2:
            quotes = ('"', "'")
            for quote in quotes:
                if xperf_path.startswith(quote) and xperf_path.endswith(quote):
                    self.config['xperf_path'] = xperf_path[1:-1]
                    break

        # fix options for --develop
        if self.config.get('develop'):
            if not self.config.get('webserver'):
                self.config['webserver'] = 'localhost:%s' % utils.findOpenPort('127.0.0.1')

        extraPrefs = self.config.pop('extraPrefs', {})
        extraPrefs = dict([(i, utils.parsePref(j)) for i, j in extraPrefs.items()])
        self.config['preferences'].update(extraPrefs)
        # remove None values from preferences;
        # allows overrides
        self.config['preferences'] = dict([(key,value)
                                           for key, value in self.config['preferences'].items()
                                           if value is not None])
        # fix talos.logfile preference to be an absolute path
        # http://hg.mozilla.org/build/talos/file/e1022c38a8ed/talos/PerfConfigurator.py#l129
        if 'talos.logfile' in self.config['preferences']:
            # if set to empty string, use the "global" browser_log
            # in practice these should always be in sync
            log_file = self.config['preferences']['talos.logfile'].strip() or self.config['browser_log']
            log_file = os.path.abspath(log_file)
            self.config['preferences']['talos.logfile'] = log_file

        if 'init_url' in self.config:
            # fix init_url
            self.config['init_url'] = self.convertUrlToRemote(self.config['init_url'])

        # get filters
        ignore_first = self.config.pop('ignore_first')
        if ignore_first:
            # BBB handle legacy ignore_first case
            # convert --ignoreFirst to the appropriate set of filters
            if self.config.get('filters'):
                raise ConfigurationError("Can't use --ignoreFirst and --filter; use --filter instead")
            self.config['filters'] = ['ignore_first', 'median']
        # convert options.filters to [[filter, [args]]]
        filters = []
        _filters = self.config.get('filters', self.filters[:])
        for position, filter_name in enumerate(_filters):
            if isinstance(filter_name, basestring):
                try:
                    f = filter.parse(filter_name)
                    # Check if last filter is scalar filter
                    # and if all the rest are series filters
                    if position == len(_filters)-1:
                        assert f[0] in filter.scalar_filters,\
                               "Last filter has to be a scalar filter."
                    else:
                        assert f[0] in filter.series_filters,\
                               "Any filter except the last has to be a series filter."
                except Exception, e:
                    raise ConfigurationError("Bad value for filter '%s': %s" % (filter_name, e))
            else:
                f = filter_name
            filters.append(f)
        self.config['filters'] = filters

        # get counters to add
        counters = set()
        for key, values in self.counters.items():
            if self.config.get(key):
                counters.update(values)

        # get tests
        # get user-selected tests
        activeTests = self.config.pop('activeTests', [])
        overrides = self.config.pop('test_overrides', {}) # test overrides from yaml file
        global_overrides = {}
        for key in self.global_overrides:
            # get global overrides for all tests
            value = self.config.pop(key, None)
            if value is not None:
                global_overrides[key] = value

        # add noChrome to global overrides (HACK)
        noChrome = self.config.pop('noChrome', None)
        if noChrome:
            global_overrides['tpchrome'] = False

        # HACK: currently xperf tests post results to graph server and we want to ensure we don't publish shutdown numbers
        # This is also hacked because "--noShutdown -> shutdown:True"
        if self.config.get('xperf_path', ''):
            global_overrides['shutdown'] = False

        if isinstance(activeTests, basestring):
            activeTests = activeTests.strip()
            activeTests = activeTests.split(':')

        # add the tests to the configuration
        # XXX extending vs over-writing?
        self.config.setdefault('tests', []).extend(self.tests(activeTests, overrides, global_overrides, counters))

        for test in self.config.get('tests', []):
            # robopan is the only robocop based extension which uses roboextender
            if self.config.get('fennecIDs', '') and test['name'] == 'trobopan':
                self.config['extensions'] = ['${talos}/mobile_extensions/roboextender@mozilla.org']

        if self.remote:
            # fix up logfile preference
            logfile = self.config['preferences'].get('talos.logfile')
            if logfile:
                # use the last part of the browser_log overridden for the remote log
                # from the global; see
                # http://hg.mozilla.org/build/talos/file/c702ff8892be/talos/remotePerfConfigurator.py#l45
                self.config['preferences']['talos.logfile'] = '%s/%s' % (self.deviceroot, os.path.basename(logfile))

            self.config['process'] = self.config['browser_path']

    def parse_args(self, *args, **kwargs):

        # parse the arguments to configuration
        options, args = Configuration.parse_args(self, *args, **kwargs)

        # print tests, if specified
        if options.print_tests:
            if self.config['tests']:
                # in order to not change self.config['tests']
                config_test_copy = copy.deepcopy(self.config['tests'])
                print '\n', '-'*80 # As a visual separator
                for config_test in config_test_copy:
                    # This is a hack to get rid of all the raw formatting in the YAML output
                    # Without this, output is all over the place and many \'s present
                    description = ' '.join(test.test_dict[config_test['name']].description().strip().split())
                    config_test['description'] = description
                    serializer = YAML()
                    serializer._write(sys.stdout, config_test)
                    print '-'*80, '\n' # As a visual separator
            else:
                print 'Available tests:'
                print '================\n'
                test_class_names = [(test_class.name(), test_class.description()) 
                                    for test_class in test.tests]
                test_class_names.sort()
                for name, description in test_class_names:                    
                    print name
                    print '-'*len(name)
                    print description
                    print # Appends a single blank line to the end
            self.exit()

        # if no tests err out
        if not self.config['tests']:
            self.error("No tests found; please specify --activeTests")

        # serialize to screen, if specified
        if options.verbose:
            serializer = YAML()
            serializer._write(sys.stdout, self.config)

        # return the arguments
        return options, args

    def dump(self, options, missingvalues):
        """
        dump the tests as specified by -o, --outputName,
        or otherwise according to the currentDateString
        """

        if not getattr(options, 'dump') and self._dump and not 'print_tests' in self.parsed:
            options.dump = "%s_config.yml" % self.currentDateString()

        # output the name for buildbot
        # http://hg.mozilla.org/build/buildbotcustom/file/97d2b407f824/steps/talos.py#l89
        outputName = getattr(options, 'dump', None)
        if outputName:
            print " - outputName = %s" % outputName

        Configuration.dump(self, options, missingvalues)

    ### PerfConfigurator methods

    def tests(self, activeTests, overrides=None, global_overrides=None, counters=None):
        """
        return a list of test dictionaries
        - activeTests: a list of test
        - overrides: a dict of dicts containing overrides for the specific tests
        - global_overrides: a dict of overrides that win over test-specifics
        - counters: counters to add to the tests
        """

        # ensure overrides of the right form
        overrides = overrides or {}
        for key, value in overrides.items():
            if not isinstance(value, dict):
                raise ConfigurationError('test overrides must be a dict: (%s, %s)' % (key, value))

        # ensure tests are available
        availableTests = test.test_dict.keys()
        if not set(activeTests).issubset(availableTests):
            missing = [i for i in activeTests
                       if i not in availableTests]
            raise ConfigurationError("No definition found for test(s): %s" % missing)

        # return the tests
        retval = []
        for test_name in activeTests:
            test_class = test.test_dict[test_name]

            # specific variables do not need overrides, in this case tpmozafterpaint
            test_instance = test_class()
            mozAfterPaint = getattr(test_instance, 'tpmozafterpaint', None)

            # add test_name_extension to config
            # http://hg.mozilla.org/build/talos/file/c702ff8892be/talos/PerfConfigurator.py#l107
            noChrome = self.config.get('noChrome')
            if noChrome or mozAfterPaint and not self.config.get('test_name_extension'):
                # (it would be nice to handle this more elegantly)
                test_name_extension = ''
                if noChrome:
                    test_name_extension += '_nochrome'
                if mozAfterPaint:
                    test_name_extension += '_paint'
                self.config['test_name_extension'] = test_name_extension


            if self.config.get('deviceroot'):
                if not test_class.mobile:
                    raise ConfigurationError("Test %s is not able to run on mobile devices at this time" % test_name)
            elif not test_class.desktop:
                raise ConfigurationError("Test %s is not able to run on desktop builds at this time" % test_name)

            # use test-specific overrides
            test_overrides = overrides.get(test_name, {})

            # use global overrides
            test_overrides.update(global_overrides or {})

            # instantiate the test
            test_instance.update(**test_overrides)

            # update original value of mozAfterPaint, this could be 'false', so check for None
            if mozAfterPaint is not None:
                test_instance.tpmozafterpaint = mozAfterPaint

            # fix up url
            url = getattr(test_instance, 'url', None)
            if url:
                test_instance.url = self.convertUrlToRemote(url)

            # fix up tpmanifest
            tpmanifest = getattr(test_instance, 'tpmanifest', None)
            if tpmanifest:
                if self.config.get('develop') or self.config.get('deviceroot'):
                    test_instance.tpmanifest = self.buildRemoteManifest(utils.interpolatePath(tpmanifest))

            # add any counters
            if counters:
                keys = ['linux_counters', 'mac_counters', 'remote_counters', 'win_counters', 'w7_counters', 'xperf_counters']
                for key in keys:
                    if key not in test_instance.keys:
                        # only populate attributes that will be output
                        continue
                    if not isinstance(getattr(test_instance, key, None), list):
                        setattr(test_instance, key, [])
                    _counters = getattr(test_instance, key)
                    _counters.extend([counter for counter in counters
                                      if counter not in _counters])

            # get its dict
            retval.append(dict(test_instance.items()))

        return retval

    def currentDateString(self):
        """standard convention format for current date string"""
        return datetime.now().strftime("%Y%m%d_%H%M")

    def convertUrlToRemote(self, url):
        """
        For a given url add a webserver.
        In addition if there is a .manifest file specified, covert
        and copy that file to the remote device.
        """

        if '://' in url:
            # assume a fully qualified url
            return url

        # get the webserver
        webserver = self.config.get('webserver')
        if not webserver:
            return url

        # We cannot load .xul remotely and winopen.xul is the only instance.
        # winopen.xul is handled in remotePerfConfigurator.py
        if '.html' in url:
            url = 'http://%s/%s' % (webserver , url)

        if 'winopen.xul' in url:
            url = 'file://' + self.deviceroot + '/talos/' + url

        if self.remote:
            # Take care of tpan/tzoom tests
            url = url.replace('webServer=', 'webServer=%s' % self.config['webserver'])

        return url

    def buildRemoteManifest(self, manifestName):
        """
        Take a given manifest name, convert the localhost->remoteserver, and then copy to the device
        returns the remote filename on the device so we can add it to the .config file
        """

        # read manifest lines
        fHandle = None
        try:
            fHandle = open(manifestName, 'r')
            manifestLines = fHandle.readlines()
            fHandle.close()
        except:
            if fHandle:
                fHandle.close()
            raise # reraise current exception; prints traceback to screen


        # write modified manifest lines
        newHandle = open(manifestName + '.develop', 'w')
        for line in manifestLines:
            newHandle.write(line.replace('localhost', self.config['webserver']))
        newHandle.close()

        newManifestName = manifestName + '.develop'

        if self.remote:
            remoteName = self.deviceroot

            remoteName += '/' + os.path.basename(manifestName)
            try:
                self.testAgent.pushFile(newManifestName, remoteName)
            except mozdevice.DMError:
                print "Remote Device Error: Unable to copy remote manifest file %s to %s" % (newManifestName, remoteName)
                raise
            return remoteName

        # return new manifest
        return newManifestName

    def output_options(self):
        """configuration related to outputs;
        Returns a 2-tuple of
        - a dictionary of output format -> urls
        - a dictionary of options for each format
        """

        outputs = ['results_urls', 'datazilla_urls']
        results_urls = dict([(key, self.config[key]) for key in outputs
                             if key in self.config])
        results_options = {}
        options = {'datazilla_urls': ['authfile']}
        for key, values in options.items():
            for item in values:
                value = self.config.get(item)
                if value:
                    results_options.setdefault(key, {})[item] = value
        return results_urls, results_options

    def browser_config(self):

        title = self.config.get('title', '')

        required = ['preferences', 'extensions',
                    'browser_path', 'browser_log', 'browser_wait',
                    'extra_args', 'buildid', 'env', 'init_url'
                    ]
        optional = {'bcontroller_config': 'bcontroller.yml',
                    'branch_name': '',
                    'child_process': 'plugin-container',
                    'develop': False,
                    'deviceroot': '',
                    'dirs': {},
                    'host': self.config.get('deviceip', ''), # XXX names should match!
                    'port': self.config.get('deviceport', ''), # XXX names should match!
                    'process': '',
                    'remote': False,
                    'fennecIDs': '',
                    'repository': 'NULL',
                    'sourcestamp': 'NULL',
                    'symbols_path': None,
                    'test_name_extension': '',
                    'test_timeout': 1200,
                    'webserver': '',
                    'xperf_path': None,
                    'error_filename': None
                    }
        browser_config = dict(title=title)
        browser_config.update(dict([(i, self.config[i]) for i in required]))
        browser_config.update(dict([(i, self.config.get(i, j)) for i, j in optional.items()]))
        return browser_config

    def _setupRemote(self, deviceip, deviceport):

        # Init remotePerfConfigurator

        # remote-specific preferences
        self.config['preferences'].update({'talos.logfile': 'browser_output.txt',
                                           'network.manage-offline-status': False})
        for pref in ('network.proxy.http',
                     'network.proxy.http_port',
                     'network.proxy.type',
                     'browser.bookmarks.max_backups',
                     'dom.max_chrome_script_run_time'):
            # remove preferences not applicable to remote
            self.config['preferences'].pop(pref, None)

        # setup remote device
        try:
            self.testAgent = utils.testAgent(deviceip, deviceport)
            if 'deviceroot' in self.config:
                self.deviceroot = self.config['deviceroot']
            else:
                self.deviceroot = self.testAgent.getDeviceRoot()
        except mozdevice.DMError:
            print "Remote Device Error: Unable to connect to remote device '%s'" % deviceip

        self.config['deviceroot'] = self.deviceroot

    def is_remote(self, args):
        """
        determines if the configuration is for testing a remote device;
        - args : dictionary of configuration to check
        """

        deviceroot = None
        deviceip = None

        for config in args:
            deviceroot = config.get('deviceroot', deviceroot)
            deviceip = config.get('deviceip', deviceip)

        if deviceroot or deviceip:
            return True
        return False

def main(args=sys.argv[1:]):

    # generate a configuration from command-line arguments
    conf = PerfConfigurator(usage='%prog [options]')

    # XXX add PerfConfigurator-specific override for load since
    # Perfconfigurator and talos console_script entry points differ
    conf.add_option("-f", "--sampleConfig", dest="load",
                    action="append",
                    help="Input config file")

    # parse the arguments and dump an output file
    options, args = conf.parse_args(args)

    if args:
        conf.error("PerfConfigurator takes no arguments")
        return 1
    return 0

if __name__ == '__main__':
    sys.exit(main())
