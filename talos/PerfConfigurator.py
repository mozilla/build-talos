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
        ('browser_path', {'help': "path to executable we are testing",
                          'required': "Please specify --executablePath",
                          'flags': ['-e', '--executablePath']
                          }),
        # --sampleConfig is handled separately
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
        ('addon_id', {'help': 'ID of the extension being tested',
                      'flags': ['--addonID']}),
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
        ('amo', {'help': 'set amo',
                 'type': bool}),
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
                                  'tpformat': 'tinderbox',
                                  'tpmozafterpaint': False,
                                  'tpnoisy': True,
                                  'tppagecycles': 1,
                                  'tprender': False,
                                  'win_counters': [],
                                  'w7_counters': [],
                                  'linux_counters': [],
                                  'mac_counters': [],
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

        ### options for remotePerfConfigurator
        ### needed here for run_tests.py
        ('deviceip', {'flags': []}),
        ('deviceport', {'flags': []}),
        ('deviceroot', {'flags': []}),
        ('fennecIDs', {'flags': []}),
        ('remote', {'flags': []})
        ]

    # default preferences to run with
    # these are updated with --extraPrefs from the commandline
    # for extension scopes, see
    # see https://developer.mozilla.org/en/Installing_extensions
    preferences = {
        'app.update.enabled': False,
        'browser.bookmarks.max_backups': 0,
        'browser.cache.disk.smart_size.enabled': False,
        'browser.cache.disk.smart_size.first_run': False,
        'browser.dom.window.dump.enabled': True,
        'browser.EULA.override': True,
        'browser.link.open_newwindow': 2,
        'browser.shell.checkDefaultBrowser': False,
        'browser.warnOnQuit': False,
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
        'toolkit.telemetry.prompted': 2
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

    # config items to extend vs overwrite
    extend = set(['basetest', 'extraPrefs'])

    # whether to dump by default
    _dump = True

    ### methods overrided from configuration.py

    def __init__(self, **kwargs):

        # add preferences to the configuration
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

    def validate(self):
        """validate and finalize configuration"""

        # generic configuration validation
        Configuration.validate(self)

        # add test_name_extension to config
        # http://hg.mozilla.org/build/talos/file/c702ff8892be/talos/PerfConfigurator.py#l107
        noChrome = self.config.get('noChrome')
        mozAfterPaint = self.config.get('tpmozafterpaint')
        if noChrome or mozAfterPaint and not self.config.get('test_name_extension'):
            # (it would be nice to handle this more elegantly)
            test_name_extension = ''
            if noChrome:
                test_name_extension += '_nochrome'
            if mozAfterPaint:
                test_name_extension += '_paint'
            self.config['test_name_extension'] = test_name_extension

        # BBB: (resultsServer, resultsLink) -> results_url
        resultsServer = self.config.pop('resultsServer', None)
        resultsLink = self.config.pop('resultsLink', None)
        if resultsServer and resultsLink:
            if self.config.get('results_urls'):
                raise Configuration("Can't user resultsServer/resultsLink and results_url: use results_url instead")
            self.config['results_urls'] = ['http://%s%s' % (resultsServer, resultsLink)]

        # default raw_results_url
        # TODO: deprecate and set via invoker (buildbot, etc)
        if not self.config.get('datazilla_urls'):
            self.config['datazilla_urls'] = ["http://10.8.73.29/views/api/load_test"]
        # include a way to disable
        if self.config['datazilla_urls'] == ['']:
            self.config['datazilla_urls'] = []

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

        # set preferences
        if self.config.get('tpmozafterpaint'):
            self.config['preferences']['dom.send_after_paint_to_content'] = True
        extraPrefs = self.config.pop('extraPrefs', {})
        extraPrefs = dict([(i, self.parsePref(j)) for i, j in extraPrefs.items()])
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
        for filter_name in _filters:
            if isinstance(filter_name, basestring):
                try:
                    f = filter.parse(filter_name)
                except Exception, e:
                    raise ConfigurationError("Bad value for filter '%s': %s" % (filter_name, e))
            else:
                f = filter_name
            filters.append(f)
        self.config['filters'] = filters

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

        if isinstance(activeTests, basestring):
            activeTests = activeTests.strip()
            activeTests = activeTests.split(':')

        # add the tests to the configuration
        # XXX extending vs over-writing?
        self.config.setdefault('tests', []).extend(self.tests(activeTests, overrides, global_overrides))

    def parse_args(self, *args, **kwargs):

        # parse the arguments to configuration
        options, args = Configuration.parse_args(self, *args, **kwargs)

        # print tests, if specified
        if options.print_tests:
            if self.config['tests']:
                serializer = YAML()
                serializer._write(sys.stdout, self.config['tests'])
            else:
                print 'Available tests:'
                for test_class in test.tests:
                    print test_class.name()
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

        if not getattr(options, 'dump') and self._dump:
            options.dump = "%s_config.yml" % self.currentDateString()

        # output the name for buildbot
        # http://hg.mozilla.org/build/buildbotcustom/file/97d2b407f824/steps/talos.py#l89
        outputName = getattr(options, 'dump', None)
        if outputName:
            print " - outputName = %s" % outputName

        Configuration.dump(self, options, missingvalues)

    ### PerfConfigurator methods

    def tests(self, activeTests, overrides=None, global_overrides=None):
        """
        return a list of test dictionaries
        - activeTests: a list of test
        - overrides: a dict of dicts containing overrides for the specific tests
        - global_overrides: a dict of overrides that win over test-specifics
        """

        # ensure overrides of the right form
        overrides = overrides or {}
        for key, value in overrides.items():
            if not isinstance(value, dict):
                raise ConfiguratonError('test overrides must be a dict: (%s, %s)' % (key, value))

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

            # use test-specific overrides
            test_overrides = overrides.get(test_name, {})

            # use global overrides
            test_overrides.update(global_overrides or {})

            # instantiate the test
            test_instance = test_class(**test_overrides)

            # fix up url
            url = getattr(test_instance, 'url', None)
            if url:
                test_instance.url = self.convertUrlToRemote(url)

            # fix up tpmanifest
            tpmanifest = getattr(test_instance, 'tpmanifest', None)
            if tpmanifest:
                if self.config.get('develop') or self.config.get('deviceroot'):
                    test_instance.tpmanifest = self.buildRemoteManifest(utils.interpolatePath(tpmanifest))

            # get its dict
            retval.append(dict(test_instance.items()))

        return retval

    def currentDateString(self):
        """standard convention format for current date string"""
        return datetime.now().strftime("%Y%m%d_%H%M")

    def convertUrlToRemote(self, url):
        """
        For a give url add a webserver.
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
            return 'http://%s/%s' % (webserver , url)
        else:
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

        # return new manifest
        return manifestName + '.develop'

    def parsePref(self, value):
        """parse a preference value from a string"""
        if not isinstance(value, basestring):
            return value
        if value.lower() == 'true':
            return True
        if value.lower() == 'false':
            return False
        try:
            return int(value)
        except ValueError:
            return value

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
