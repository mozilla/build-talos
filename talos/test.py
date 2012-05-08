"""
test prototypes for Talos
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

    def __str__(self):
        lines = ["- name: %s" % self.name()]
        for key in self.keys:
            value = getattr(self, key, None)
            if value is not None:
                lines.append('  %s: %s' % (key, value))
        return '\n'.join(lines)

class TestSequel(Test):
    """abstract class to handle names in the form of 'tdhtml.2'"""
    @classmethod
    def name(cls):
        name = cls.__name__
        if '_' in name:
            name = '.'.join(name.rsplit('_', 1))
        return name

### ts-style tests

class TsBase(Test):
    """abstract base class for ts-style tests"""
    keys = ['url', 'url_timestamp', 'timeout', 'cycles', 'shutdown', 'profile_path', 'xperf_providers', 'xperf_stackwalk']

class ts(TsBase):
    cycles = 20
    timeout = 150
    url = 'startup_test/startup_test.html?begin='
    url_timestamp = True
    shutdown = True

class ts_paint(ts):
    url = 'startup_test/tspaint_test.html?begin='
    shutdown = None

class ts_places_generated_max(ts):
    profile_path = '${talos}/places_generated_max'
    timeout = None

class ts_places_generated_min(ts):
    profile_path = '${talos}/places_generated_min'
    timeout = None

class ts_places_generated_med(ts):
    profile_path = '${talos}/places_generated_med'
    timeout = None

class twinopen(TsBase):
    url = 'startup_test/twinopen/winopen.xul?phase1=20'
    timeout = 300

class tpaint(TsBase):
    url = 'startup_test/twinopen/winopen.xul?mozafterpaint=1%26phase1=20'
    timeout = 300

# mobile ts-type tests

class tpan(TsBase):
    url = 'startup_test/fennecmark/fennecmark.html?test=PanDown%26webServer='
    cycles = 10
    timeout = 300

class tzoom(TsBase):
    url = 'startup_test/fennecmark/fennecmark.html?test=Zoom%26webServer='
    cycles = 10
    timeout = 300

class trobopan(TsBase):
    url = 'am instrument -w -e class org.mozilla.fennec.tests.testPan org.mozilla.roboexample.test/android.test.InstrumentationTestRunner'
    cycles = 5
    timeout = 300

class tcheckerboard(TsBase):
    url = 'am instrument -w -e class org.mozilla.fennec.tests.testCheck org.mozilla.roboexample.test/android.test.InstrumentationTestRunner'
    cycles = 5
    timeout = 300

class tprovider(TsBase):
    url = 'am instrument -w -e class org.mozilla.fennec.tests.testBrowserProviderPerf org.mozilla.roboexample.test/android.test.InstrumentationTestRunner'
    cycles = 5
    timeout = 300

class tcheck2(TsBase):
    url = 'am instrument -w -e class org.mozilla.fennec.tests.testCheck2 org.mozilla.roboexample.test/android.test.InstrumentationTestRunner'
    cycles = 5
    timeout = 300

class tcheck3(TsBase):
    url = 'am instrument -w -e class org.mozilla.fennec.tests.testCheck3 org.mozilla.roboexample.test/android.test.InstrumentationTestRunner'
    cycles = 5
    timeout = 300

### pageloader tests

class PageloaderTest(Test):
    """abstract base class for a Talos Pageloader test"""
    tpmanifest = None # test manifest
    tpcycles = 1 # number of time to run each page
    cycles = None
    timeout = None
    keys = ['tpmanifest', 'tpcycles', 'tppagecycles', 'tprender', 'tpchrome',
            'rss', 'resolution', 'cycles',
            'win_counters', 'w7_counters', 'linux_counters', 'mac_counters', 'remote_counters',
            'timeout', 'shutdown', 'responsiveness', 'profile_path',
            'xperf_providers', 'xperf_stackwalk'
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

class tp4(tp):
    tpmanifest = '${talos}/page_load_test/tp4.manifest'

class tp4m(tp4):
    tpmanifest = '${talos}/page_load_test/tp4m.manifest'
    tpcycles = 2
    win_counters = w7_counters = linux_counters = mac_counters = None
    remote_counters = ['Main_RSS', 'Content_RSS']
    timeout = 14400

class tp5(tp):
    tpmanifest = '${talos}/page_load_test/tp5/tp5.manifest'

class tp5r(tp5):
    rss = True
    cycles = 1
    responsiveness = False
    profile_path = '${talos}/base_profile'

class tp5row(tp5):
    tpcycles = 1
    tppagecycles = 25
    rss = True
    win_counters = ['Main_RSS', 'Content_RSS', 'Private Bytes', '% Processor Time']
    w7_counters = ['Main_RSS', 'Content_RSS', 'Private Bytes', '% Processor Time', 'Modified Page List Bytes']
    linux_counters = ['Private Bytes', 'XRes', 'Main_RSS', 'Content_RSS']
    mac_counters = ['Private Bytes', 'Main_RSS', 'Content_RSS']

class tp_js(PageloaderTest):
    url = """'"http://localhost/page_load_test/framecycler.html?quit=1&cycles=5"'"""
    win_counters = ['Working Set', 'Private Bytes', '% Processor Time']
    w7_counters = ['Working Set', 'Private Bytes', '% Processor Time', 'Modified Page List Bytes']
    linux_counters = ['Private Bytes', 'RSS', 'XRes']
    mac_counters = ['Private Bytes', 'RSS']
    keys = ['url', 'win_counters', 'w7_counters', 'linux_counters', 'mac_counters']

class tdhtml(PageloaderTest):
    tpmanifest = '${talos}/page_load_test/dhtml/dhtml.manifest'
    tpcycles = 5

class tsvg(PageloaderTest):
    tpmanifest = '${talos}/page_load_test/svg/svg.manifest'
    tpcycles = 5

class tsvg_opacity(tsvg):
    tpmanifest = '${talos}/page_load_test/svg_opacity/svg_opacity.manifest'

class v8(PageloaderTest):
    tpmanifest = '${talos}/page_load_test/v8/v8.manifest'
    tpcycles = 20
    resolution = 20

class tsspider(PageloaderTest):
    """sunspider pageloader test"""
    tpmanifest = '${talos}/page_load_test/sunspider/sunspider.manifest'
    tpcycles = 5

class tscroll(PageloaderTest):
    tpmanifest = '${talos}/page_load_test/scroll/scroll.manifest'
    tpcycles = 5

class dromaeo_css(PageloaderTest):
    tpmanifest = '${talos}/page_load_test/dromaeo/css.manifest'

class dromaeo_dom(PageloaderTest):
    tpmanifest = '${talos}/page_load_test/dromaeo/dom.manifest'

class dromaeo_jslib(PageloaderTest):
    tpmanifest = '${talos}/page_load_test/dromaeo/jslib.manifest'

class dromaeo_sunspider(PageloaderTest):
    tpmanifest = '${talos}/page_load_test/dromaeo/sunspider.manifest'

class dromaeo_v8(PageloaderTest):
    tpmanifest = '${talos}/page_load_test/dromaeo/v8.manifest'

class dromaeo_basics(PageloaderTest):
    tpmanifest = '${talos}/page_load_test/dromaeo/dromaeo.manifest'

class a11y(PageloaderTest):
    tpmanifest = '${talos}/page_load_test/a11y/a11y.manifest'
    tpcycles = 5

### test sequels

class tdhtml_2(TestSequel, tdhtml):
    pass

class tsvg_2(TestSequel, tsvg):
    pass

class tsvg_opacity_2(TestSequel, tsvg_opacity):
    pass

class v8_2(TestSequel, v8):
    pass

class tsspider_2(TestSequel, tsspider):
    pass

class tscroll_2(TestSequel, tscroll):
    pass

class a11y_2(TestSequel, a11y):
    tpcycles = 1

# global test data

tests = [ts, ts_paint,
         ts_places_generated_max, ts_places_generated_min, ts_places_generated_med,
         tp, tp4, tp4m, tp5, tp5r, tp5row, tp_js,
         tdhtml, tsvg, tsvg_opacity,
         v8, tpaint, twinopen, tsspider, tscroll,
         tpan, tzoom, trobopan, tcheckerboard, tprovider, tcheck2,
         dromaeo_css, dromaeo_dom, dromaeo_jslib, dromaeo_sunspider, dromaeo_v8, dromaeo_basics,
         a11y,
         tdhtml_2, tsvg_2, tsvg_opacity_2, v8_2, tsspider_2, tscroll_2, a11y_2
         ]
test_dict = dict([(i.name(), i) for i in tests])

if __name__ == '__main__':
    import optparse
    parser = optparse.OptionParser()

    options, args = parser.parse_args()

    if not args:
        print 'Available tests:'
        for test in tests:
            print test.name()

    missing = [i for i in args if i not in test_dict]
    if missing:
        parser.error("Unknown tests: %s" % ', '.join(missing))

    for arg in args:
        test = test_dict[arg]()
        print str(test)
