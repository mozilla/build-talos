"""
test definitions for Talos
"""

class Test(object):
    """abstract base class for a Talos test case"""
    cycles = None # number of cycles
    keys = []
    desktop = True
    mobile = True

    @classmethod
    def name(cls):
        return cls.__name__

    @classmethod
    def description(cls):
        if cls.__doc__ == None:
            return "No documentation available yet."
        else:
            doc = cls.__doc__
            description_lines = [i.strip() for i in doc.strip().splitlines()]
            return "\n".join(description_lines)

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



### ts-style tests (ts, twinopen, ts_cold, etc)
### The overall test number is calculated by excluding the max opening time
### and taking an average of the remaining numbers. 

class TsBase(Test):
    """abstract base class for ts-style tests"""
    keys = ['url', 'url_timestamp', 'timeout', 'cycles', 'shutdown', 'profile_path', 'xperf_counters',
            'xperf_providers', 'xperf_user_providers', 'xperf_stackwalk']

class ts(TsBase):
    """
    A basic start up test (ts = test start up)
    
    The overall test number is calculated by excluding the max opening time 
    and taking an average of the remaining numbers. 
    Unlike ts_paint, ts test uses a blank profile.
    """
    cycles = 20
    timeout = 150
    url = 'startup_test/startup_test.html?begin='
    url_timestamp = True
    shutdown = True

class ts_paint(ts):
    """
    Launches tspaint_test.html with the current timestamp in the url,
    waits for [MozAfterPaint and onLoad] to fire, then records the end
    time and calculates the time to startup.
    """
    url = 'startup_test/tspaint_test.html?begin='
    shutdown = None
    xperf_counters = ['main_startup_fileio', 'main_startup_netio', 'main_normal_fileio', 'main_normal_netio', 'main_shutdown_fileio', 'main_shutdown_netio', 'nonmain_startup_fileio', 'nonmain_startup_netio', 'nonmain_normal_fileio', 'nonmain_shutdown_fileio', 'nonmain_shutdown_netio']

class tspaint_places_generated_max(ts_paint):
    """
    Runs the same test as ts_paint, but uses a generated profile to
    simulate what a power user would have. This profile is very outdated
    and needs to be updated. 
    """
    profile_path = '${talos}/places_generated_max'
    timeout = None
    mobile = False # This depends on a custom profile and mobile requires it's own profile

class tspaint_places_generated_med(ts_paint):
    """
    Runs the same test as ts_paint, but uses a generated profile to
    simulate what an average user would have. This profile is very
    outdated and needs to be updated. 
    """
    profile_path = '${talos}/places_generated_med'
    timeout = None
    mobile = False # This depends on a custom profile and mobile requires it's own profile

class tpaint(TsBase):
    """
    Tests the amount of time it takes the open a new window. This test does
    not include startup time. Multiple test windows are opened in succession,
    results reported are the average amount of time required to create and 
    display a window in the running instance of the browser. 
    (Measures ctrl-n performance.) 
    """
    url = 'file://${talos}/startup_test/twinopen/winopen.xul?mozafterpaint=1%26phase1=20'
    timeout = 300
    mobile = False # XUL based tests with local files.

class tresize(TsBase):
    """
    This test does some resize thing.
    """
    cycles = 20
    url = 'startup_test/tresize-test.html'
    timeout = 150
    filters = [['mean', []]]

# mobile ts-type tests
class trobopan(TsBase):
    """
    Panning performance test. Value is square of frame delays (ms greater
    than 25 ms) encountered while panning. Lower values are better.
    """
    url = 'am instrument -w -e deviceroot %s -e class org.mozilla.fennec.tests.testPan org.mozilla.roboexample.test/org.mozilla.fennec.FennecInstrumentationTestRunner'
    cycles = 5
    timeout = 300
    desktop = False

class tcheckerboard(TsBase):
    """
    Simple measure of 'checkerboarding'. Lower values are better.
    """
    url = 'am instrument -w -e deviceroot %s -e class org.mozilla.fennec.tests.testCheck org.mozilla.roboexample.test/org.mozilla.fennec.FennecInstrumentationTestRunner'
    cycles = 5
    timeout = 300
    desktop = False

class tprovider(TsBase):
    """
    A mobile ts_type test (docstring to be updated)
    """
    url = 'am instrument -w -e deviceroot %s -e class org.mozilla.fennec.tests.testBrowserProviderPerf org.mozilla.roboexample.test/org.mozilla.fennec.FennecInstrumentationTestRunner'
    cycles = 5
    timeout = 300
    desktop = False

class tcheck2(TsBase):
    """
    Measure of 'checkerboarding' during simulation of real user interaction
    with page. Lower values are better.
    """
    url = 'am instrument -w -e deviceroot %s -e class org.mozilla.fennec.tests.testCheck2 org.mozilla.roboexample.test/org.mozilla.fennec.FennecInstrumentationTestRunner'
    cycles = 5
    timeout = 300
    desktop = False

### pageloader tests(tp5, tdhtml, etc)

### The overall test number is determined by first calculating the median
### page load time for each page in the set (excluding the max page load 
### per individual page). The max median from that set is then excluded and
### the average is taken; that becomes the number reported to the tinderbox
### waterfall. 

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
    """
    Base class for all tp based tests (tp = test pageload)
    
    The original tp test created by Mozilla to test browser page load time. 
    Cycled through 40 pages. The pages were copied from the live web during 
    November, 2000. Pages were cycled by loading them within the main 
    browser window from a script that lived in content.
    """
    tpmanifest = '${talos}/page_load_test/tp3.manifest'
    tpcycles = None
    resolution = 20
    win_counters = ['Working Set', 'Private Bytes', '% Processor Time']
    w7_counters = ['Working Set', 'Private Bytes', '% Processor Time', 'Modified Page List Bytes']
    linux_counters = ['Private Bytes', 'RSS', 'XRes']
    mac_counters = ['Private Bytes', 'RSS']
    shutdown = True

class tp4m(tp):
    """
    This is a smaller pageset (21 pages) of the updated web page test which 
    was set to 100 pages from February 2009. It is designed for mobile 
    Firefox and is a blend of regular and mobile friendly pages.
    """
    tpmanifest = '${talos}/page_load_test/tp4m.manifest'
    tpcycles = 2
    win_counters = w7_counters = linux_counters = mac_counters = None
    remote_counters = ['Main_RSS']
    timeout = 14400

class tp5n(tp):
    """
    Tests the time it takes Firefox to load the tp5 web page test set.
    
    The tp5 is an updated web page test set to 100 pages from April 8th, 2011.
    Effort was made for the pages to no longer be splash screens/login 
    pages/home pages but to be pages that better reflect the actual content 
    of the site in question. 
    """
    tpmanifest = '${talos}/page_load_test/tp5n/tp5n.manifest'
    tpcycles = 1
    tppagecycles = 25
    rss = True
    win_counters = ['Main_RSS', 'Private Bytes', '% Processor Time']
    w7_counters = ['Main_RSS', 'Private Bytes', '% Processor Time', 'Modified Page List Bytes']
    linux_counters = ['Private Bytes', 'XRes', 'Main_RSS']
    mac_counters = ['Private Bytes', 'Main_RSS']
    xperf_counters = ['main_startup_fileio', 'main_startup_netio', 'main_normal_fileio', 'main_normal_netio', 'main_shutdown_fileio', 'main_shutdown_netio', 'nonmain_startup_fileio', 'nonmain_normal_fileio']
    mobile = False # too many files to run, we will hit OOM

class tdhtml(PageloaderTest):
    """
    Tests which measure the time to cycle through a set of DHTML test pages.
    This test will be updated in the near future. 
    This test is also ran with the nochrome option. 
    """
    tpmanifest = '${talos}/page_load_test/dhtml/dhtml.manifest'
    tpcycles = 5

class tsvg(PageloaderTest):
    """
    An svg-only number that measures SVG rendering performance. 
    """
    tpmanifest = '${talos}/page_load_test/svg/svg.manifest'
    tpcycles = 5

class tsvg_opacity(PageloaderTest):
    """
    An svg-only number that measures SVG rendering performance. 
    """
    tpmanifest = '${talos}/page_load_test/svg_opacity/svg_opacity.manifest'
    tpcycles = 5

class v8_7(PageloaderTest):
    """
    This is the V8 (version 7) javascript benchmark taken verbatim and
    slightly modified to fit into our pageloader extension and talos harness.

    The previous version of this test is V8 version 5 which was run on
    selective branches and operating systems. 
    """
    tpmanifest = '${talos}/page_load_test/v8_7/v8.manifest'
    tpcycles = 1
    resolution = 20

class kraken(PageloaderTest):
    """
    This is the Kraken javascript benchmark taken verbatim and slightly
    modified to fit into our pageloader extension and talos harness.     
    """
    tpmanifest = '${talos}/page_load_test/kraken/kraken.manifest'
    tpcycles = 1
    tppagecycles = 1
    filters = [['mean', []]]

class tscroll(PageloaderTest):
    """
    This test does some scrolly thing.
    """
    tpmanifest = '${talos}/page_load_test/scroll/scroll.manifest'
    tpcycles = 5

class dromaeo(PageloaderTest):
    """abstract base class for dramaeo tests"""
    filters = [['dromaeo', []]]

class dromaeo_css(dromaeo):
    """
    Dromaeo suite of tests for JavaScript performance testing.
    See the Dromaeo wiki (https://wiki.mozilla.org/Dromaeo)
    for more information.
    
    Each page in the manifest is part of the dromaemo css benchmark. 
    """
    tpmanifest = '${talos}/page_load_test/dromaeo/css.manifest'

class dromaeo_dom(dromaeo):
    """
    Dromaeo suite of tests for JavaScript performance testing.
    See the Dromaeo wiki (https://wiki.mozilla.org/Dromaeo)
    for more information.
    
    Each page in the manifest is part of the dromaemo dom benchmark. 
    """
    tpmanifest = '${talos}/page_load_test/dromaeo/dom.manifest'

class a11y(PageloaderTest):
    """
    This test ensures basic a11y tables and permutations do not cause
    performance regressions. 
    """
    tpmanifest = '${talos}/page_load_test/a11y/a11y.manifest'
    tpcycles = 5
    mobile = False # we don't make a11y.manifest have urls, it just has dhtml.html instead of http://ip:port/dhtml.html

# 'r' tests are row based vs column based.
class tdhtmlr(tdhtml):
    """
    Tests which measure the time to cycle through a set of DHTML test pages.
    This test will be updated in the near future. Unlike tdhtml, this test 
    is row-based instead of column based.
    This test is also ran with the nochrome option. 
    """
    tpcycles = 1
    tppagecycles = 25

class tsvgr(tsvg):
    """
    Like the tsvg test this is an svg-only number that measures SVG
    rendering performance. Unlike tsvg, this test is row-based instead
    of column based.
    """
    tpcycles = 1
    tppagecycles = 25

class tsvgr_opacity(tsvg_opacity):
    """
    Like the tsvg_opacity test this is an svg-only number that measures SVG
    rendering performance. Unlike tsvg_opacity, this test is row-based 
    instead of column based.
    """
    tpcycles = 1
    tppagecycles = 25

class tscrollr(PageloaderTest):
    """
    Like tscroll, this test does some scrolly thing. Unlike tscroll, this
    test is row-based instead of column based.
    """
    tpmanifest = '${talos}/page_load_test/scroll/scroll.manifest'
    tpcycles = 1
    tppagecycles = 25

class a11yr(PageloaderTest):
    """
    Like a11y, this test ensures basic a11y tables and permutations do not
    cause performance regressions. Unlike a11y, this test is row-based
    instead of column based.
    """
    tpmanifest = '${talos}/page_load_test/a11y/a11y.manifest'
    tpcycles = 1
    tppagecycles = 25
    mobile = False # we don't make a11y.manifest have urls, it just has dhtml.html instead of http://ip:port/dhtml.html

# global test data
tests = [ts_paint, ts, tsvg, tdhtml,
         tspaint_places_generated_max, tspaint_places_generated_med,
         tp4m, tp5n, tpaint, tresize,
         trobopan, tcheckerboard, tprovider, tcheck2,
         dromaeo_css, dromaeo_dom, v8_7, kraken,
         tdhtmlr, tsvgr, tsvgr_opacity, tscrollr, a11yr
         ]
test_dict = dict([(i.name(), i) for i in tests])
