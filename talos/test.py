"""
test definitions for Talos
"""

class Test(object):
    """abstract base class for a Talos test case"""
    cycles = None # number of cycles
    keys = []

    @classmethod
    def name(cls):
        return cls.__name__

    def __init__(self, **kw):
        self.__dict__.update(kw)

    def items(self):
        """
        returns a list of 2-tuples
        """
        retval = [('name', self.name())]
        for key in self.keys:
            value = getattr(self, key, None)
            if value is not None:
                retval.append((key, value))
        return retval

    def __str__(self):
        """string form appropriate for YAML output"""
        items = self.items()

        key, value = items.pop(0)
        lines = ["- %s: %s" % (key, value)]
        for key, value in items:
            lines.append('  %s: %s' % (key, value))
        return '\n'.join(lines)


### ts-style tests

class TsBase(Test):
    """abstract base class for ts-style tests"""
    keys = ['url', 'url_timestamp', 'timeout', 'cycles', 'shutdown', 'profile_path', 'xperf_counters',
            'xperf_providers', 'xperf_user_providers', 'xperf_stackwalk']

class ts(TsBase):
    cycles = 20
    timeout = 150
    url = 'startup_test/startup_test.html?begin='
    url_timestamp = True
    shutdown = True

class ts_paint(ts):
    url = 'startup_test/tspaint_test.html?begin='
    shutdown = None
    xperf_counters = ['main_startup_fileio', 'main_startup_netio', 'main_normal_fileio', 'main_normal_netio', 'main_shutdown_fileio', 'main_shutdown_netio', 'nonmain_startup_fileio', 'nonmain_startup_netio', 'nonmain_normal_fileio', 'nonmain_normal_netio', 'nonmain_shutdown_fileio', 'nonmain_shutdown_netio']

class tspaint_places_generated_max(ts_paint):
    profile_path = '${talos}/places_generated_max'
    timeout = None

class tspaint_places_generated_med(ts_paint):
    profile_path = '${talos}/places_generated_med'
    timeout = None

class tpaint(TsBase):
    url = 'startup_test/twinopen/winopen.xul?mozafterpaint=1%26phase1=20'
    timeout = 300

class tresize(TsBase):
    cycles = 20
    url = 'startup_test/tresize-test.html'
    timeout = 150
    filters = [['mean', []]]

# mobile ts-type tests
class trobopan(TsBase):
    url = 'am instrument -w -e deviceroot %s -e class org.mozilla.fennec.tests.testPan org.mozilla.roboexample.test/org.mozilla.fennec.FennecInstrumentationTestRunner'
    cycles = 5
    timeout = 300

class tcheckerboard(TsBase):
    url = 'am instrument -w -e deviceroot %s -e class org.mozilla.fennec.tests.testCheck org.mozilla.roboexample.test/org.mozilla.fennec.FennecInstrumentationTestRunner'
    cycles = 5
    timeout = 300

class tprovider(TsBase):
    url = 'am instrument -w -e deviceroot %s -e class org.mozilla.fennec.tests.testBrowserProviderPerf org.mozilla.roboexample.test/org.mozilla.fennec.FennecInstrumentationTestRunner'
    cycles = 5
    timeout = 300

class tcheck2(TsBase):
    url = 'am instrument -w -e deviceroot %s -e class org.mozilla.fennec.tests.testCheck2 org.mozilla.roboexample.test/org.mozilla.fennec.FennecInstrumentationTestRunner'
    cycles = 5
    timeout = 300

class tcheck3(TsBase):
    url = 'am instrument -w -e deviceroot %s -e class org.mozilla.fennec.tests.testCheck3 org.mozilla.roboexample.test/org.mozilla.fennec.FennecInstrumentationTestRunner'
    cycles = 5
    timeout = 300

### pageloader tests

class PageloaderTest(Test):
    """abstract base class for a Talos Pageloader test"""
    tpmanifest = None # test manifest
    tpcycles = 1 # number of time to run each page
    cycles = None
    timeout = None
    filters = None
    keys = ['tpmanifest', 'tpcycles', 'tppagecycles', 'tprender', 'tpchrome', 'tpmozafterpaint',
            'rss', 'resolution', 'cycles',
            'win_counters', 'w7_counters', 'linux_counters', 'mac_counters', 'remote_counters', 'xperf_counters',
            'timeout', 'shutdown', 'responsiveness', 'profile_path',
            'xperf_providers', 'xperf_user_providers', 'xperf_stackwalk', 'filters'
            ]

class tp(PageloaderTest):
    tpmanifest = '${talos}/page_load_test/tp3.manifest'
    tpcycles = None
    resolution = 20
    win_counters = ['Working Set', 'Private Bytes', '% Processor Time']
    w7_counters = ['Working Set', 'Private Bytes', '% Processor Time', 'Modified Page List Bytes']
    linux_counters = ['Private Bytes', 'RSS', 'XRes']
    mac_counters = ['Private Bytes', 'RSS']
    shutdown = True

class tp4m(tp):
    tpmanifest = '${talos}/page_load_test/tp4m.manifest'
    tpcycles = 2
    win_counters = w7_counters = linux_counters = mac_counters = None
    remote_counters = ['Main_RSS', 'Content_RSS']
    timeout = 14400

class tp5n(tp):
    tpmanifest = '${talos}/page_load_test/tp5n/tp5n.manifest'
    tpcycles = 1
    tppagecycles = 25
    rss = True
    win_counters = ['Main_RSS', 'Content_RSS', 'Private Bytes', '% Processor Time']
    w7_counters = ['Main_RSS', 'Content_RSS', 'Private Bytes', '% Processor Time', 'Modified Page List Bytes']
    linux_counters = ['Private Bytes', 'XRes', 'Main_RSS', 'Content_RSS']
    mac_counters = ['Private Bytes', 'Main_RSS', 'Content_RSS']
    xperf_counters = ['main_startup_fileio', 'main_startup_netio', 'main_normal_fileio', 'main_normal_netio', 'main_shutdown_fileio', 'main_shutdown_netio', 'nonmain_startup_fileio', 'nonmain_startup_netio', 'nonmain_normal_fileio', 'nonmain_normal_netio', 'nonmain_shutdown_fileio', 'nonmain_shutdown_netio']

class tdhtml(PageloaderTest):
    tpmanifest = '${talos}/page_load_test/dhtml/dhtml.manifest'
    tpcycles = 5

class tsvg(PageloaderTest):
    tpmanifest = '${talos}/page_load_test/svg/svg.manifest'
    tpcycles = 5

class tsvg_opacity(PageloaderTest):
    tpmanifest = '${talos}/page_load_test/svg_opacity/svg_opacity.manifest'
    tpcycles = 5

class v8_7(PageloaderTest):
    tpmanifest = '${talos}/page_load_test/v8_7/v8.manifest'
    tpcycles = 1
    resolution = 20

class sunspider(PageloaderTest):
    """sunspider 0.9.1 test"""
    tpmanifest = '${talos}/page_load_test/sunspider091/sunspider.manifest'
    tpcycles = 1
    tppagecycles = 1
    filters = [['mean', []]]

class kraken(PageloaderTest):
    """Kraken test"""
    tpmanifest = '${talos}/page_load_test/kraken/kraken.manifest'
    tpcycles = 1
    tppagecycles = 1
    filters = [['mean', []]]

class tscroll(PageloaderTest):
    tpmanifest = '${talos}/page_load_test/scroll/scroll.manifest'
    tpcycles = 5

class dromaeo(PageloaderTest):
    """abstract base class for dramaeo tests"""
    filters = [['dromaeo', []]]

class dromaeo_css(dromaeo):
    tpmanifest = '${talos}/page_load_test/dromaeo/css.manifest'

class dromaeo_dom(dromaeo):
    tpmanifest = '${talos}/page_load_test/dromaeo/dom.manifest'

class a11y(PageloaderTest):
    tpmanifest = '${talos}/page_load_test/a11y/a11y.manifest'
    tpcycles = 5

# 'r' tests are row based vs column based.
class tdhtmlr(tdhtml):
    tpcycles = 1
    tppagecycles = 25

class tsvgr(tsvg):
    tpcycles = 1
    tppagecycles = 25

class tsvgr_opacity(tsvg_opacity):
    tpcycles = 1
    tppagecycles = 25

class tscrollr(PageloaderTest):
    tpmanifest = '${talos}/page_load_test/scroll/scroll.manifest'
    tpcycles = 1
    tppagecycles = 25

class a11yr(PageloaderTest):
    tpmanifest = '${talos}/page_load_test/a11y/a11y.manifest'
    tpcycles = 1
    tppagecycles = 25

# global test data
tests = [ts_paint, ts, tsvg, tdhtml,
         tspaint_places_generated_max, tspaint_places_generated_med,
         tp4m, tp5n, tpaint, tresize,
         trobopan, tcheckerboard, tprovider, tcheck2, tcheck3,
         dromaeo_css, dromaeo_dom, v8_7, sunspider, kraken,
         tdhtmlr, tsvgr, tsvgr_opacity, tscrollr, a11yr
         ]
test_dict = dict([(i.name(), i) for i in tests])
