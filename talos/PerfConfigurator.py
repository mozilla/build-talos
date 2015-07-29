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
import socket
import test
import utils
from configuration import Configuration
from configuration import YAML
from datetime import datetime


__all__ = ['ConfigurationError', 'PerfConfigurator', 'main']


class ConfigurationError(Exception):
    """error when parsing Talos configuration"""


class PerfConfigurator(Configuration):
    options = [
        ('browser_path', {
            'help': "path to executable we are testing",
            'flags': ['-e', '--executablePath']
        }),
        ('title', {
            'help': 'Title of the test run',
            'default': 'qm-pxp01',
            'flags': ['-t', '--title']
        }),
        ('branch_name', {
            'help': 'Name of the branch we are testing on',
            'default': '',
            'flags': ['--branchName']
        }),
        ('browser_wait', {
            'help': 'Amount of time allowed for the browser to cleanly close',
            'default': 5,
            'flags': ['-w', '--browserWait']
        }),
        ('results_urls', {
            'help': 'DEPRECATED, will be removed soon.',
            'flags': ['--results_url'],
            'type': list
        }),

        # XXX activeTests should really use a list-thingy but can't because of
        # the one-off ':' separation :/
        ('activeTests', {
            'help': "List of tests to run, separated by ':' (ex. damp:cart)",
            'flags': ['-a', '--activeTests']
        }),
        ('e10s', {
            'help': 'enable e10s',
            'type': bool,
            'flags': ['--e10s']
        }),
        ('noChrome',  {
            'help': 'do not run tests as chrome',
            'type': bool
        }),
        ('rss', {
            'help': "Collect RSS counters from pageloader instead of the"
                    " operating system",
            'type': bool
        }),
        ('mainthread', {
            'help': "Collect mainthread IO data from the browser by setting"
                    " an environment variable",
            'type': bool
        }),
        ('tpmozafterpaint', {
            'help': 'wait for MozAfterPaint event before recording the time',
            'type': bool,
            'flags': ['--mozAfterPaint']
        }),
        ('sps_profile', {
            'help': 'Profile the run and output the results in'
                    ' $MOZ_UPLOAD_DIR',
            'type': bool,
            'flags': ['--spsProfile']
        }),
        ('sps_profile_interval', {
            'help': 'How frequently to take samples (ms)',
            'type': int,
            'flags': ['--spsProfileInterval']
        }),
        ('sps_profile_entries', {
            'help': 'How many samples to take with the profiler',
            'type': int,
            'flags': ['--spsProfileEntries']
        }),
        ('extensions', {
            'help': 'Extension to install while running',
            'default': ['${talos}/talos-powers',
                        '${talos}/pageloader'],
            'flags': ['--extension']
        }),
        ('fast', {'help': 'Run tp tests as tp_fast', 'type': bool}),
        ('symbols_path', {
            'help': 'Path to the symbols for the build we are testing',
            'flags': ['--symbolsPath']
        }),
        ('xperf_path', {'help': 'Path to windows performance tool xperf.exe'}),
        ('test_timeout', {
            'help': 'Time to wait for the browser to output to the log file',
            'default': 1200
        }),
        ('browser_log', {
            'help': 'Local log file to store the output from the browser in',
            'default': 'browser_output.txt',
            'flags': ['--logFile']
        }),
        ('error_filename', {
            'help': 'Filename to store the errors found during the test.'
                    ' Currently used for xperf only.',
            'default': os.path.abspath('browser_failures.txt'),
            'flags': ['--errorFile']
        }),
        ('shutdown', {
            'help': 'Record time browser takes to shutdown after testing',
            'type': bool,
            'flags': ['--noShutdown']
        }),
        ('extraPrefs', {
            'help': 'defines an extra user preference',
            # TODO: metavar = "PREF=VALUE"
            'default': {},
            'flags': ['--setPref']
        }),
        ('webserver', {
            'help': 'address of the webserver hosting the talos files',
            'flags': ['--webServer']
        }),
        ('develop', {
            'help': "useful for running tests on a developer machine."
                    " Creates a local webserver and doesn't upload to the"
                    " graph servers.",
            'default': False
        }),
        ('responsiveness', {
            'help': 'turn on responsiveness collection',
            'type': bool
        }),
        ('filters', {
            'help': 'filters to apply to the data from talos.filters [DEFAULT:'
                    ' ignore_max, median]',
            'type': list,
            'flags': ['--filter']
        }),
        ('cycles', {'help': 'number of browser cycles to run', 'type': int}),
        ('tpmanifest', {'help': 'manifest file to test'}),
        ('tpcycles', {
            'help': 'number of pageloader cycles to run',
            'type': int
        }),
        ('tptimeout', {
            'help': 'number of milliseconds to wait for a load event after'
                    ' calling loadURI before timing out',
            'type': int
        }),
        ('tppagecycles', {
            'help': 'number of pageloader cycles to run for each page in'
                    ' the manifest',
            'type': int
        }),
        ('tpdelay', {'help': 'length of the pageloader delay', 'type': int}),
        ('sourcestamp',  {
            'help': 'Specify the hg revision or sourcestamp for the changeset'
                    ' we are testing.  This will use the value found in'
                    ' application.ini if it is not specified.'
        }),
        ('repository',  {
            'help': 'Specify the url for the repository we are testing. '
                    'This will use the value found in application.ini if'
                    ' it is not specified.'
        }),

        # arguments without command line options
        ('extra_args', {
            'help': 'arguments to pass to browser',
            'default': '',
            'flags': []
        }),
        ('bcontroller_config', {
            'help': 'path to YAML input for bcontroller',
            'default': '${talos}/bcontroller.yml',
            'flags': []
        }),
        ('buildid', {'default': 'testbuildid', 'flags': []}),
        ('init_url', {'default': 'getInfo.html', 'flags': []}),
        ('dirs', {'default': {}, 'flags': []}),
        ('env', {'default': {'NO_EM_RESTART': '1'}, 'flags': []}),
        ('basetest', {
            'help': 'base data for all tests',
            'default': {
                'cycles': 1,
                'test_name_extension': '',
                'profile_path': '${talos}/base_profile',
                'responsiveness': False,
                'e10s': False,
                'sps_profile': False,
                'sps_profile_interval': 1,
                'sps_profile_entries': 100000,
                'resolution': 1,
                'rss': False,
                'mainthread': False,
                'shutdown': False,
                'timeout': 3600,
                'tpchrome': True,
                'tpcycles': 10,
                'tpmozafterpaint': False,
                'tpdisable_e10s': False,
                'tpnoisy': True,
                'tppagecycles': 1,
                'tploadnocache': False,
                'tpscrolltest': False,
                'tprender': False,
                'win_counters': [],
                'w7_counters': [],
                'linux_counters': [],
                'mac_counters': [],
                'xperf_counters': [],
                'setup': None,
                'cleanup': None
            },
            'flags': []
        }),
        ('test_overrides', {
            'help': 'test overrides from .config file',
            'type': dict,
            'flags': []
        }),
        ('test_name_extension', {
            'help': 'test name extension',
            'flags': []
        }),
        ('process', {'help': 'process name', 'flags': []}),
        ('tests', {'help': 'tests to run', 'flags': []}),
    ]

    # default preferences to run with
    # these are updated with --extraPrefs from the commandline
    # for extension scopes, see
    # see https://developer.mozilla.org/en/Installing_extensions
    preferences = {
        'app.update.enabled': False,
        'browser.addon-watch.interval': -1,  # Deactivate add-on watching
        'browser.aboutHomeSnippets.updateUrl':
            'https://127.0.0.1/about-dummy/',
        'browser.bookmarks.max_backups': 0,
        'browser.cache.disk.smart_size.enabled': False,
        'browser.cache.disk.smart_size.first_run': False,
        'browser.chrome.dynamictoolbar': False,
        'browser.dom.window.dump.enabled': True,
        'browser.EULA.override': True,
        'browser.link.open_newwindow': 2,
        'browser.reader.detectedFirstArticle': True,
        'browser.shell.checkDefaultBrowser': False,
        'browser.warnOnQuit': False,
        'browser.tabs.remote.autostart': False,
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
        'xpinstall.signatures.required': False,
        'hangmonitor.timeout': 0,
        'network.proxy.http': 'localhost',
        'network.proxy.http_port': 80,
        'network.proxy.type': 1,
        'security.enable_java': False,
        'security.fileuri.strict_origin_policy': False,
        'toolkit.telemetry.prompted': 999,
        'toolkit.telemetry.notifiedOptOut': 999,
        'dom.send_after_paint_to_content': True,
        'security.turn_off_all_security_so_that_viruses_can_'
        'take_over_this_computer': True,
        'browser.newtabpage.directory.source':
            '${webserver}/directoryLinks.json',
        'browser.newtabpage.directory.ping': '',
        'browser.newtabpage.introShown': True,
        'browser.safebrowsing.gethashURL':
            'http://127.0.0.1/safebrowsing-dummy/gethash',
        'browser.safebrowsing.keyURL':
            'http://127.0.0.1/safebrowsing-dummy/newkey',
        'browser.safebrowsing.updateURL':
            'http://127.0.0.1/safebrowsing-dummy/update',
        'browser.safebrowsing.enabled': False,
        'browser.safebrowsing.malware.enabled': False,
        'browser.search.isUS': True,
        'browser.search.countryCode': 'US',
        'browser.selfsupport.url':
            'https://127.0.0.1/selfsupport-dummy/',
        'extensions.update.url':
            'http://127.0.0.1/extensions-dummy/updateURL',
        'extensions.update.background.url':
            'http://127.0.0.1/extensions-dummy/updateBackgroundURL',
        'extensions.blocklist.enabled': False,
        'extensions.blocklist.url':
            'http://127.0.0.1/extensions-dummy/blocklistURL',
        'extensions.hotfix.url':
            'http://127.0.0.1/extensions-dummy/hotfixURL',
        'extensions.update.enabled': False,
        'extensions.webservice.discoverURL':
            'http://127.0.0.1/extensions-dummy/discoveryURL',
        'extensions.getAddons.maxResults': 0,
        'extensions.getAddons.get.url':
            'http://127.0.0.1/extensions-dummy/repositoryGetURL',
        'extensions.getAddons.getWithPerformance.url':
            'http://127.0.0.1/extensions-dummy'
            '/repositoryGetWithPerformanceURL',
        'extensions.getAddons.search.browseURL':
            'http://127.0.0.1/extensions-dummy/repositoryBrowseURL',
        'extensions.getAddons.search.url':
            'http://127.0.0.1/extensions-dummy/repositorySearchURL',
        'plugins.update.url':
            'http://127.0.0.1/plugins-dummy/updateCheckURL',
        'media.gmp-manager.url':
            'http://127.0.0.1/gmpmanager-dummy/update.xml',
        'media.navigator.enabled': True,
        'media.peerconnection.enabled': True,
        'media.navigator.permission.disabled': True,
        'media.capturestream_hints.enabled': True,
        'browser.contentHandlers.types.0.uri': 'http://127.0.0.1/rss?url=%s',
        'browser.contentHandlers.types.1.uri': 'http://127.0.0.1/rss?url=%s',
        'browser.contentHandlers.types.2.uri': 'http://127.0.0.1/rss?url=%s',
        'browser.contentHandlers.types.3.uri': 'http://127.0.0.1/rss?url=%s',
        'browser.contentHandlers.types.4.uri': 'http://127.0.0.1/rss?url=%s',
        'browser.contentHandlers.types.5.uri': 'http://127.0.0.1/rss?url=%s',
        'identity.fxaccounts.auth.uri': 'https://127.0.0.1/fxa-dummy/',
        'datareporting.healthreport.about.reportUrl':
            'http://127.0.0.1/abouthealthreport/',
        'datareporting.healthreport.documentServerURI':
            'http://127.0.0.1/healthreport/',
        'datareporting.policy.dataSubmissionPolicyBypassNotification': True,
        'general.useragent.updates.enabled': False,
        'browser.webapps.checkForUpdates': 0,
        'browser.search.geoSpecificDefaults': False,
        'browser.snippets.enabled': False,
        'browser.snippets.syncPromo.enabled': False,
        'toolkit.telemetry.server': 'https://127.0.0.1/telemetry-dummy/',
        'experiments.manifest.uri':
            'https://127.0.0.1/experiments-dummy/manifest',
        'network.http.speculative-parallel-limit': 0,
        'browser.displayedE10SPrompt': 9999,
        'browser.displayedE10SPrompt.1': 9999,
        'browser.displayedE10SPrompt.2': 9999,
        'browser.displayedE10SPrompt.3': 9999,
        'browser.displayedE10SPrompt.4': 9999,
        'browser.displayedE10SPrompt.5': 9999,
        'app.update.badge': False,
        'lightweightThemes.selectedThemeID': "",
        'devtools.webide.widget.enabled': False,
        'devtools.webide.widget.inNavbarByDefault': False,
        'devtools.chrome.enabled': False,
        'devtools.debugger.remote-enabled': False,
        'devtools.theme': "light",
        'devtools.timeline.enabled': False,
        'identity.fxaccounts.migrateToDevEdition': False
    }

    # keys to generated self.config that are global overrides to tests
    global_overrides = ['cycles',
                        'test_name_extension',
                        'responsiveness',
                        'sps_profile',
                        'sps_profile_interval',
                        'sps_profile_entries',
                        'rss',
                        'mainthread',
                        'shutdown',
                        'tpcycles',
                        'tpdelay',
                        'tppagecycles',
                        'tpmanifest',
                        'tptimeout',
                        'tpmozafterpaint',
                        'tpdisable_e10s'
                        ]

    # default filters
    filters = ['ignore_max', 'median']

    # counters turned on by CLI options
    counters = {'rss': ['Main_RSS'],
                'mainthreadio': ['mainthread_io']}

    # config items to extend vs overwrite
    extend = set(['basetest', 'extraPrefs'])

    # whether to dump by default
    _dump = True

    # methods overridden from configuration.py

    def __init__(self, **kwargs):

        # add preferences to the configuration
        # TODO: do at class level
        self.options.append(('preferences', {'help': 'browser preferences',
                                             'default': self.preferences,
                                             'flags': []}))

        # set arguments to dump to a configuration file
        kwargs.setdefault('dump', ['-o', '--output'])

        # set usage argument
        kwargs.setdefault(
            'usage',
            '%(prog)s [options] manifest.yml [manifest.yml] [...]'
        )

        # call parent constructor
        Configuration.__init__(self, **kwargs)

    def argparse_options(self, parser):
        Configuration.argparse_options(self, parser)

        # PerfConfigurator specific options
        # to use used only in parse_args
        parser.add_argument('-v', '--verbose', dest='verbose',
                            action='store_true', default=False,
                            help="Dump configuration to stdout")
        parser.add_argument('--print-tests', dest='print_tests',
                            action='store_true', default=False,
                            help="Print the resulting tests configuration to"
                                 " stdout (or print available tests if"
                                 " --activeTests not specified)")

    def validate(self):
        """validate and finalize configuration"""

        # generic configuration validation
        Configuration.validate(self)

        # ensure the browser_path is specified
        msg = "Please specify --executablePath"
        if 'print_tests' not in self.parsed and \
                not self.config.get('browser_path'):
            self.error(msg)

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
            if not os.path.exists(self.config.get('xperf_path')):
                raise ConfigurationError(
                    "xperf.exe cannot be found at the path specified")

        # fix options for --develop
        if self.config.get('develop'):
            if not self.config.get('webserver'):
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(("127.0.0.1", 15707))
                self.config['webserver'] = 'localhost:%s' % s.getsockname()[1]

        # if e10s is enabled, set prefs accordingly
        if self.config.get('e10s'):
            self.config['preferences']['browser.tabs.remote.autostart'] = True
        else:
            self.config['preferences']['browser.tabs.remote.autostart'] = False
            self.config['preferences']['browser.tabs.remote.autostart.1'] = \
                False
            self.config['preferences']['browser.tabs.remote.autostart.2'] = \
                False

        extraPrefs = self.config.pop('extraPrefs', {})
        extraPrefs = dict([(i, utils.parse_pref(j))
                           for i, j in extraPrefs.items()])
        self.config['preferences'].update(extraPrefs)
        # remove None values from preferences;
        # allows overrides
        self.config['preferences'] = dict(
            [(key, value)
             for key, value in self.config['preferences'].items()
             if value is not None]
        )
        # fix talos.logfile preference to be an absolute path
        # http://hg.mozilla.org/build/talos/file/e1022c38a8ed/talos
        # /PerfConfigurator.py#l129
        if 'talos.logfile' in self.config['preferences']:
            # if set to empty string, use the "global" browser_log
            # in practice these should always be in sync
            log_file = self.config['preferences']['talos.logfile'].strip() or \
                self.config['browser_log']
            log_file = os.path.abspath(log_file)
            self.config['preferences']['talos.logfile'] = log_file

        # TODO: Investigate MozillaFileLogger and stability on OSX 10.6 and
        # Win7 hack here to not set logfile - this will break tp5n-xperf
        #  so we don't do it there
        if 'talos.logfile' in self.config['preferences']:
            if not xperf_path:
                del self.config['preferences']['talos.logfile']

        if 'init_url' in self.config:
            # fix init_url
            self.config['init_url'] = \
                self.convertUrlToRemote(self.config['init_url'])

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
                            "Any filter except the last has to be a"\
                            " series filter."
                except Exception, e:
                    raise ConfigurationError(
                        "Bad value for filter '%s': %s" % (filter_name, e))
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
        if isinstance(activeTests, basestring):
            activeTests = activeTests.strip()
            activeTests = activeTests.split(':')
        # temporary hack for now until we have e10s running on all tests;
        # please remove if you are running locally
        if self.config.get('e10s'):
            for testname in ['sessionrestore',
                             'sessionrestore_no_auto_restore']:
                if testname in activeTests:
                    print "%s is unsupported on e10s, removing from list of " \
                        "tests to run" % testname
                    activeTests.remove(testname)

        # test overrides from yaml file
        overrides = self.config.pop('test_overrides', {})
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

        # HACK: currently xperf tests post results to graph server and
        # we want to ensure we don't publish shutdown numbers
        # This is also hacked because "--noShutdown -> shutdown:True"
        if self.config.get('xperf_path', ''):
            global_overrides['shutdown'] = False

        # add the tests to the configuration
        # XXX extending vs over-writing?
        self.config.setdefault('tests', []).extend(
            self.tests(activeTests, overrides, global_overrides, counters))

    def parse_args(self, *args, **kwargs):

        # parse the arguments to configuration
        args = Configuration.parse_args(self, *args, **kwargs)

        # print tests, if specified
        if args.print_tests:
            if self.config['tests']:
                # in order to not change self.config['tests']
                config_test_copy = copy.deepcopy(self.config['tests'])
                print '\n', '-'*80  # As a visual separator
                for config_test in config_test_copy:
                    # This is a hack to get rid of all the raw formatting in
                    # the YAML output. Without this, output is all over the
                    # place and many \'s present
                    description = ' '.join(
                        test.test_dict()[config_test['name']]
                        .description().strip().split()
                    )
                    config_test['description'] = description
                    serializer = YAML()
                    serializer._write(sys.stdout, config_test)
                    print '-'*80, '\n'  # As a visual separator
            else:
                print 'Available tests:'
                print '================\n'
                test_class_names = [
                    (test_class.name(), test_class.description())
                    for test_class in test.test_dict().itervalues()
                ]
                test_class_names.sort()
                for name, description in test_class_names:
                    print name
                    print '-'*len(name)
                    print description
                    print  # Appends a single blank line to the end
            self.exit()

        # if no tests err out
        if not self.config['tests']:
            self.error("No tests found; please specify --activeTests")

        # serialize to screen, if specified
        if args.verbose:
            serializer = YAML()
            serializer._write(sys.stdout, self.config)

        # return the arguments
        return args

    def dump(self, options, missingvalues):
        """
        dump the tests as specified by -o, --outputName,
        or otherwise according to the currentDateString
        """

        if not getattr(options, 'dump') and self._dump and \
                'print_tests' not in self.parsed:
            options.dump = "%s_config.yml" % self.currentDateString()

        # output the name for buildbot
        # http://hg.mozilla.org/build/buildbotcustom/file
        # /97d2b407f824/steps/talos.py#l89
        outputName = getattr(options, 'dump', None)
        if outputName:
            print " - outputName = %s" % outputName

        Configuration.dump(self, options, missingvalues)

    # PerfConfigurator methods

    def tests(self, activeTests, overrides=None, global_overrides=None,
              counters=None):
        """
        return a list of test dictionaries
        - activeTests: a list of test
        - overrides: a dict of dicts containing overrides for the specific
                     tests
        - global_overrides: a dict of overrides that win over test-specifics
        - counters: counters to add to the tests
        """

        # ensure overrides of the right form
        overrides = overrides or {}
        for key, value in overrides.items():
            if not isinstance(value, dict):
                raise ConfigurationError(
                    'test overrides must be a dict: (%s, %s)' % (key, value))

        test_dict = test.test_dict()

        # ensure tests are available
        availableTests = test_dict.keys()
        if not set(activeTests).issubset(availableTests):
            missing = [i for i in activeTests
                       if i not in availableTests]
            raise ConfigurationError("No definition found for test(s): %s"
                                     % missing)

        # return the tests
        retval = []
        for test_name in activeTests:
            test_class = test_dict[test_name]

            # specific variables do not need overrides, in this case
            # tpmozafterpaint
            test_instance = test_class()
            mozAfterPaint = getattr(test_instance, 'tpmozafterpaint', None)

            # add test_name_extension to config
            # http://hg.mozilla.org/build/talos/file/c702ff8892be/talos
            # /PerfConfigurator.py#l107
            noChrome = self.config.get('noChrome')
            if noChrome or mozAfterPaint:
                # (it would be nice to handle this more elegantly)
                test_name_extension = ''
                if noChrome:
                    test_name_extension += '_nochrome'
                if mozAfterPaint:
                    test_name_extension += '_paint'
                test_instance.test_name_extension = test_name_extension

            elif not test_class.desktop:
                raise ConfigurationError(
                    "Test %s is not able to run on desktop builds at this time"
                    % test_name
                )

            # use test-specific overrides
            test_overrides = overrides.get(test_name, {})

            # use global overrides
            test_overrides.update(global_overrides or {})

            # instantiate the test
            test_instance.update(**test_overrides)

            # update original value of mozAfterPaint, this could be 'false',
            # so check for None
            if mozAfterPaint is not None:
                test_instance.tpmozafterpaint = mozAfterPaint

            # fix up url
            url = getattr(test_instance, 'url', None)
            if url:

                test_instance.url = utils.interpolate(
                    self.convertUrlToRemote(url)
                )

            # fix up tpmanifest
            tpmanifest = getattr(test_instance, 'tpmanifest', None)
            if tpmanifest:
                if self.config.get('develop'):
                    test_instance.tpmanifest = \
                        self.buildRemoteManifest(
                            utils.interpolate(tpmanifest))

            # add any counters
            if counters:
                keys = ['linux_counters', 'mac_counters',
                        'win_counters', 'w7_counters', 'xperf_counters']
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
        """

        # get the webserver
        webserver = self.config.get('webserver')
        if not webserver:
            return url

        if '://' in url:
            # assume a fully qualified url
            return url

        # We cannot load .xul remotely and winopen.xul is the only instance.
        # winopen.xul is handled in remotePerfConfigurator.py
        if '.html' in url:
            url = 'http://%s/%s' % (webserver, url)

        return url

    def buildRemoteManifest(self, manifestName):
        # read manifest lines
        with open(manifestName, 'r') as fHandle:
            manifestLines = fHandle.readlines()

        # write modified manifest lines
        with open(manifestName + '.develop', 'w') as newHandle:
            for line in manifestLines:
                newHandle.write(line.replace('localhost',
                                             self.config['webserver']))

        newManifestName = manifestName + '.develop'

        # return new manifest
        return newManifestName

    def browser_config(self):

        title = self.config.get('title', '')

        required = ['preferences', 'extensions',
                    'browser_path', 'browser_log', 'browser_wait',
                    'extra_args', 'buildid', 'env', 'init_url']
        optional = {'bcontroller_config': 'bcontroller.yml',
                    'branch_name': '',
                    'child_process': 'plugin-container',
                    'develop': False,
                    'dirs': {},
                    'e10s': False,
                    'process': '',
                    'repository': None,
                    'sourcestamp': None,
                    'symbols_path': None,
                    'test_name_extension': '',
                    'test_timeout': 1200,
                    'webserver': '',
                    'xperf_path': None,
                    'error_filename': None,
                    }
        browser_config = dict(title=title)
        browser_config.update(dict([(i, self.config[i]) for i in required]))
        browser_config.update(dict([(i, self.config.get(i, j))
                              for i, j in optional.items()]))
        return browser_config


def main(args=sys.argv[1:]):

    # generate a configuration from command-line arguments
    conf = PerfConfigurator(usage='%(prog)s [options]')

    # XXX add PerfConfigurator-specific override for load since
    # Perfconfigurator and talos console_script entry points differ
    conf.add_argument("-f", "--sampleConfig", dest="load",
                      action="append",
                      help="Input config file")

    # parse the arguments and dump an output file
    args = conf.parse_args(args)

    return 0

if __name__ == '__main__':
    sys.exit(main())
