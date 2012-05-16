#!/usr/bin/env python

"""
test talos' filter module:

http://hg.mozilla.org/build/talos/file/tip/talos/filter.py
"""

import os
import sys
import tempfile
import time
import unittest
import talos.filter
from talos.run_tests import send_to_graph
from talos.PerfConfigurator import PerfConfigurator

class TestFilter(unittest.TestCase):

    data = range(30) # test data

    def test_ignore(self):
        """test the ignore filter"""
        # a bit of a stub sanity test for a single filter

        filtered = talos.filter.ignore_first(self.data)
        self.assertEquals(filtered, self.data[1:])

        filtered = talos.filter.ignore_first(self.data, 10)
        self.assertEquals(filtered, self.data[10:])

        # short series won't be filtered
        filtered = talos.filter.ignore_first(self.data, 50)
        self.assertEquals(filtered, self.data)

    def test_getting_filters(self):
        """test getting a list of filters from a string"""

        filter_names = ['ignore_max', 'ignore_max', 'max']

        # get the filter functions
        filters = talos.filter.filters(*filter_names)
        self.assertEquals(len(filter_names), len(filters))
        for filter in filters:
            self.assertTrue(self, hasattr(filter, '__call__'))

        # apply them on the data
        filtered = talos.filter.apply(self.data, filters)
        self.assertEquals(filtered, 27)

    def test_parse(self):
        """test the filter name parse function"""

        # an example with no arguments
        parsed = talos.filter.parse('mean')
        self.assertEquals(parsed, ['mean', []])

        # an example with one integer argument
        parsed = talos.filter.parse('ignore_first:10')
        self.assertEquals(parsed, ['ignore_first', [10]])
        self.assertEquals(type(parsed[1][0]), int)
        self.assertNotEqual(type(parsed[1][0]), float)

        # an example with several arguments
        parsed = talos.filter.parse('foo:10.1,2,5.0,6.')
        self.assertEquals(parsed, ['foo', [10.1, 2, 5.0, 6.0]])
        for index in (2,3):
            self.assertEquals(type(parsed[1][index]), float)
            self.assertNotEqual(type(parsed[1][index]), int)

        # an example that should fail
        self.assertRaises(ValueError, talos.filter.parse, 'foo:bar')
        self.assertRaises(ValueError, talos.filter.parse, 'foo:1,')

    def test_per_test_filters(self):
        """test to ensure that you can have per-test filters"""

        # results is defined in run_tests.py:run_tests

        # dromeao_css tests have results that look like
        results = [["""
_x_x_mozilla_page_load
_x_x_mozilla_page_load_details
|i|pagename|runs|
|0;dojo.html;5079.82
|1;ext.html;12772.22
|2;jquery.html;5236.92
|3;mootools.html;4444.92
|4;prototype.html;4546.85
|5;yui.html;3733.67
"""],
                   [{}],
                   'tpformat',
                   {'cycles': 1,
                    'filters': [['mean', []]],
                    'linux_counters': [],
                    'mac_counters': [],
                    'name': 'dromaeo_css',
                    'profile_path': '/home/jhammel/mozilla/src/talos/src/talos/talos/base_profile',
                    'resolution': 1,
                    'responsiveness': False,
                    'rss': False,
                    'shutdown': False,
                    'timeout': 3600,
                    'tpchrome': True,
                    'tpcycles': 1,
                    'tpformat': 'tinderbox',
                    'tpmanifest': 'file:/home/jhammel/mozilla/src/talos/src/talos/talos/page_load_test/dromaeo/css.manifest.develop',
                    'tpmozafterpaint': False,
                    'tpnoisy': True,
                    'tppagecycles': 1,
                    'tprender': False,
                    'url': '-tp file:/home/jhammel/mozilla/src/talos/src/talos/talos/page_load_test/dromaeo/css.manifest.develop -tpchrome -tpnoisy -tpformat tinderbox -tpcycles 1 -tppagecycles 1',
                    'w7_counters': [],
                    'win_counters': []}]

        # browser config is rather elaborate:
        # see bug 755374
        browser_config = {'addon_id': 'NULL',
                          'bcontroller_config': '/home/jhammel/mozilla/src/talos/src/talos/talos/bcontroller.yml',
                          'branch_name': '',
                          'browser_log': 'browser_output.txt',
                          'browser_name': 'Firefox',
                          'browser_path': '/home/jhammel/firefox/firefox',
                          'browser_version': '15.0a1',
                          'browser_wait': 5,
                          'buildid': '20120515030518',
                          'child_process': 'plugin-container',
                          'command': '/home/jhammel/firefox/firefox  -profile /tmp/tmpb5nsk5/profile -tp file:/home/jhammel/mozilla/src/talos/src/talos/talos/page_load_test/dromaeo/css.manifest.develop -tpchrome -tpnoisy -tpformat tinderbox -tpcycles 1 -tppagecycles 1',
                          'develop': True,
                          'deviceroot': '',
                          'dirs': {},
                          'env': {'NO_EM_RESTART': '1'},
                          'extensions': ['/home/jhammel/mozilla/src/talos/src/talos/talos/pageloader'],
                          'extra_args': '',
                          'fennecIDs': '',
                          'host': '',
                          'init_url': 'http://localhost:15707/getInfo.html',
                          'port': '',
                          'preferences': {'browser.EULA.override': True,
                                          'browser.bookmarks.max_backups': 0,
                                          'browser.cache.disk.smart_size.enabled': False,
                                          'browser.cache.disk.smart_size.first_run': False,
                                          'browser.dom.window.dump.enabled': True,
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
                                          'security.fileuri.strict_origin_policy': False},
                          'process': 'firefox',
                          'remote': False,
                          'repository': 'http://hg.mozilla.org/mozilla-central',
                          'sourcestamp': '0c78207fc93f',
                          'symbols_path': None,
                          'test_name_extension': '',
                          'test_timeout': 1200,
                          'testname': 'dromaeo_css',
                          'title': 'qm-pxp01',
                          'webserver': 'localhost:15707',
                          'xperf_path': None}

        # get a configuration object
        _conf = {'activeTests': ['ts'], 'browser_path': 'a/bogus/path'}
        conf = PerfConfigurator()
        conf(_conf)

        # make a file for results
        filename = tempfile.mktemp()

        # bogus filter
        def bogus(series):
            return 0

        # get a configuration object for dromaeo_css,
        # a pageloader style test
        _conf = {'activeTests': ['dromaeo_css'], 'browser_path': 'a/bogus/path',
                 'results_url': 'file://%s' % filename,
                 'title': 'bogustitle',
                 'date': time.time()}
        send_to_graph(_conf['results_url'], _conf['title'], _conf['date'],
                      browser_config, results={'dromaeo_css': results}, amo=False, filters=[[bogus, []]])
        self.assertTrue(os.path.exists(filename))

        page_results = {'dojo.html': 5079.82,
                        'ext.html': 12772.22,
                        'jquery.html': 5236.92,
                        'mootools.html': 4444.92,
                        'prototype.html': 4546.85,
                        'yui.html': 3733.67
                        }

        lines = [i.strip() for i in file(filename).readlines() if i.strip()]
        lines = lines[3:-1]
        lines = [line.split(',') for line in lines]
        output_results = dict([(k,float(j)) for i,j,k in lines])
        self.assertEqual(page_results, output_results)

        # Now show what happens if we don't override
        os.remove(filename)
        results[-1].pop('filters')
        send_to_graph(_conf['results_url'], _conf['title'], _conf['date'],
                      browser_config, results={'dromaeo_css': results}, amo=False, filters=[[bogus, []]])
        self.assertTrue(os.path.exists(filename))
        lines = [i.strip() for i in file(filename).readlines() if i.strip()]
        lines = lines[3:-1]
        lines = [line.split(',') for line in lines]
        output_results = dict([(k,float(j)) for i,j,k in lines])
        page_results = dict([(i, 0.) for i in page_results.keys()])
        self.assertEqual(output_results, page_results)
        os.remove(filename)

if __name__ == '__main__':
    unittest.main()
