"""
test definitions for Talos
"""

class Test(object):
    """abstract base class for a Talos test case"""
    cycles = None # number of cycles
    keys = []
    desktop = True
    mobile = True
    fennecIDs = False

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
        self.update(**kw)

    def update(self, **kw):
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



### ts-style startup tests (ts, twinopen, ts_cold, etc)
### The overall test number is calculated by excluding the max opening time
### and taking an average of the remaining numbers.

class TsBase(Test):
    """abstract base class for ts-style tests"""
    keys = [
        'url',
        'url_timestamp',
        'timeout',
        'cycles',
        'shutdown',      # If True, collect data on shutdown (using the value
                         # provided by __startTimestamp/__endTimestamp).
                         # Otherwise, ignore shutdown data
                         # (__startTimestamp/__endTimestamp is still
                         # required but ignored).
        'profile_path',  # The path containing the template profile. This directory
                         # is copied to the temporary profile during initialization of
                         # the test. If some of the files may be overwritten by Firefox
                         # and need to be reinstalled before each pass, use key |reinstall|
        'sps_profile',
        'sps_profile_interval',
        'sps_profile_entries',
        'sps_profile_startup',
        'preferences',
        'xperf_counters',
        'xperf_providers',
        'xperf_user_providers',
        'xperf_stackwalk',
        'tpmozafterpaint',
        'test_name_extension',
        'extensions',
        'setup',
        'cleanup',
        'fennecIDs',
        'reinstall',     # A list of files from the profile directory that should be copied to
                         # the temporary profile prior to running each cycle, to avoid one cycle
                         # overwriting the data used by the next another cycle (may be used e.g. for
                         # sessionstore.js to ensure that all cycles use the exact same sessionstore.js,
                         # rather than a more recent copy).
    ]


class ts(TsBase):
    """
    A basic start up test (ts = test start up)

    The overall test number is calculated by excluding the max opening time
    and taking an average of the remaining numbers.
    Unlike ts_paint, ts test uses a blank profile.
    """
    cycles = 20
    timeout = 150
    sps_profile_startup = True
    sps_profile_entries = 10000000
    url = 'startup_test/startup_test.html'
    shutdown = True

class ts_paint(ts):
    """
    Launches tspaint_test.html with the current timestamp in the url,
    waits for [MozAfterPaint and onLoad] to fire, then records the end
    time and calculates the time to startup.
    """
    url = 'startup_test/tspaint_test.html'
    shutdown = False
    xperf_counters = []
    win7_counters = []
    filters = [["ignore_first", [1]], ['median', []]]
    tpmozafterpaint = True
    rss = False
    mainthread = False
    responsiveness = False

class ts_paint_cold(ts_paint):
    """
    Clears the disk cache before running the ts_paint tests.
    """
    setup = "${talos}/startup_test/cold/setup.py"
    mobile = False

class tpaint(TsBase):
    """
    Tests the amount of time it takes the open a new window. This test does
    not include startup time. Multiple test windows are opened in succession,
    results reported are the average amount of time required to create and
    display a window in the running instance of the browser.
    (Measures ctrl-n performance.)
    """
    url = 'file://${talos}/startup_test/tpaint.html?auto=1'
    timeout = 300
    mobile = False # XUL based tests with local files.
    sps_profile_interval = 1
    sps_profile_entries = 2000000
    tpmozafterpaint = True
    filters = [["ignore_first", [5]], ['median', []]]

class tresize(TsBase):
    """
    This test does some resize thing.
    """
    extensions = '${talos}/startup_test/tresize/addon'
    cycles = 20
    url = 'startup_test/tresize/addon/content/tresize-test.html'
    timeout = 150
    sps_profile_interval = 2
    sps_profile_entries = 1000000
    tpmozafterpaint = True
    filters = [["ignore_first", [5]], ['median', []]]

# mobile ts-type tests
class trobopan(TsBase):
    """
    Panning performance test. Value is square of frame delays (ms greater
    than 25 ms) encountered while panning. Lower values are better.
    """
    url = 'am instrument -w -e deviceroot %s -e class ${robocopTestPackage}.tests.testPan ${robocopTestName}/${robocopTestPackage}.FennecInstrumentationTestRunner'
    cycles = 5
    timeout = 300
    desktop = False
    tpchrome = False
    fennecIDs = True

class tcheckerboard(TsBase):
    """
    Simple measure of 'checkerboarding'. Lower values are better.
    """
    url = 'am instrument -w -e deviceroot %s -e class ${robocopTestPackage}.tests.testCheck ${robocopTestName}/${robocopTestPackage}.FennecInstrumentationTestRunner'
    cycles = 5
    timeout = 300
    desktop = False
    tpchrome = False
    fennecIDs = True

class tprovider(TsBase):
    """
    A mobile ts_type test (docstring to be updated)
    """
    url = 'am instrument -w -e deviceroot %s -e class ${robocopTestPackage}.tests.testBrowserProviderPerf ${robocopTestName}/${robocopTestPackage}.FennecInstrumentationTestRunner'
    cycles = 5
    timeout = 300
    desktop = False
    tpchrome = False
    fennecIDs = True

class tcheck2(TsBase):
    """
    Measure of 'checkerboarding' during simulation of real user interaction
    with page. Lower values are better.
    """
    url = 'am instrument -w -e deviceroot %s -e class ${robocopTestPackage}.tests.testCheck2 ${robocopTestName}/${robocopTestPackage}.FennecInstrumentationTestRunner'
    cycles = 5
    timeout = 300
    desktop = False
    tpchrome = False
    fennecIDs = True

class sessionrestore(ts):
    """
    A start up test measuring the time it takes to load a sessionstore.js file.

    1. Set up Firefox to restore from a given sessionstore.js file.
    2. Launch Firefox.
    3. Measure the delta between firstPaint and sessionRestored.
    """
    cycles = 10
    timeout = 1000000
    sps_profile_entries = 10000000
    profile_path = '${talos}/startup_test/sessionrestore/profile'
    url = 'startup_test/sessionrestore/index.html'
    shutdown = False
    reinstall = ['sessionstore.js']
    # Restore the session
    preferences = { 'browser.startup.page': 3 }

class sessionrestore_no_auto_restore(sessionrestore):
    """
    A start up test measuring the time it takes to load a sessionstore.js file.

    1. Set up Firefox to *not* restore automatically from sessionstore.js file.
    2. Launch Firefox.
    3. Measure the delta between firstPaint and sessionRestored.
    """
    # Restore about:home
    preferences = { 'browser.startup.page': 1 }

### Media Test
class media_tests(TsBase):
    """
    Media Performance Tests
    """
    cycles = 5
    desktop = True
    mobile = False
    url = 'http://localhost:16932/startup_test/media/html/media_tests.html'
    timeout = 360

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
    keys = ['tpmanifest', 'tpcycles', 'tppagecycles', 'tprender', 'tpchrome', 'tpmozafterpaint', 'tploadnocache',
            'rss', 'mainthread', 'resolution', 'cycles', 'sps_profile', 'sps_profile_interval', 'sps_profile_entries',
            'tptimeout', 'win_counters', 'w7_counters', 'linux_counters', 'mac_counters', 'tpscrolltest',
            'remote_counters', 'xperf_counters', 'timeout', 'shutdown', 'responsiveness', 'profile_path',
            'xperf_providers', 'xperf_user_providers', 'xperf_stackwalk', 'filters', 'preferences',
            'extensions', 'setup', 'cleanup','fennecIDs', 'test_name_extension'
            ]

class tart(PageloaderTest):
    """
    Tab Animation Regression Test
    Tests tab animation on these cases:
    1. Simple: single new tab of about:blank open/close without affecting (shrinking/expanding) other tabs.
    2. icon: same as above with favicons and long title instead of about:blank.
    3. Newtab: newtab open with thumbnails preview - without affecting other tabs, with and without preload.
    4. Fade: opens a tab, then measures fadeout/fadein (tab animation without the overhead of opening/closing a tab).
    - Case 1 is tested with DPI scaling of 1.
    - Case 2 is tested with DPI scaling of 1.0 and 2.0.
    - Case 3 is tested with the default scaling of the test system.
    - Case 4 is tested with DPI scaling of 2.0 with the "icon" tab (favicon and long title).
    - Each animation produces 3 test results:
      - error: difference between the designated duration and the actual completion duration from the trigger.
      - half: average interval over the 2nd half of the animation.
      - all: average interval over all recorded intervals.
    """
    tpmanifest = '${talos}/page_load_test/tart/tart.manifest'
    extensions = '${talos}/page_load_test/tart/addon'
    tpcycles = 1
    tppagecycles = 25
    tploadnocache = True
    tpmozafterpaint = False
    sps_profile_interval = 10
    sps_profile_entries = 1000000
    win_counters = w7_counters = linux_counters = mac_counters = remote_counters = None
    """ ASAP mode """
    """ The recording API is broken with OMTC before ~2013-11-27 """
    """ After ~2013-11-27, disabling OMTC will also implicitly disable OGL HW composition """
    """ to disable OMTC with older firefox builds, also set 'layers.offmainthreadcomposition.enabled': False """
    preferences = {'layout.frame_rate': 0,
                   'docshell.event_starvation_delay_hint': 1,
                   'dom.send_after_paint_to_content': False}
    filters = [["ignore_first", [1]], ['median', []]]

class cart(PageloaderTest):
    """
    Customize Animation Regression Test
    Tests Australis customize animations (default DPI scaling). Uses the TART addon but with a different URL.
    Reports the same animation values as TART (.half/.all/.error).
    All comments for TART also apply here (e.g. for ASAP+OMTC, etc)
    Subtests are:
    1-customize-enter - from triggering customize mode until it's ready for the user
    2-customize-exit  - exiting customize
    3-customize-enter-css - only the CSS animation part of entering customize
    """
    tpmanifest = '${talos}/page_load_test/tart/cart.manifest'
    extensions = '${talos}/page_load_test/tart/addon'
    tpcycles = 1
    tppagecycles = 25
    tploadnocache = True
    tpmozafterpaint = False
    sps_profile_interval = 1
    sps_profile_entries = 10000000
    win_counters = w7_counters = linux_counters = mac_counters = remote_counters = None
    """ ASAP mode """
    preferences = {'layout.frame_rate': 0,
                   'docshell.event_starvation_delay_hint': 1,
                   'dom.send_after_paint_to_content': False}
    filters = [["ignore_first", [1]], ['median', []]]

class glterrain(PageloaderTest):
    """
    Simple rotating WebGL scene with moving light source over a textured terrain.
    Measures average frame intervals.
    The same sequence is measured 4 times for combinations of alpha and antialias as canvas properties.
    Each of these 4 runs is reported as a different test name.
    """
    tpmanifest = '${talos}/page_load_test/webgl/glterrain.manifest'
    tpcycles = 1
    tppagecycles = 25
    tploadnocache = True
    tpmozafterpaint = False
    sps_profile_interval = 10
    sps_profile_entries = 2000000
    win_counters = w7_counters = linux_counters = mac_counters = remote_counters = None
    """ ASAP mode """
    preferences = {'layout.frame_rate': 0,
                   'docshell.event_starvation_delay_hint': 1,
                   'dom.send_after_paint_to_content': False}
    filters = [["ignore_first", [1]], ['median', []]]

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
    linux_counters = ['Private Bytes', 'Main_RSS', 'XRes']
    mac_counters = ['Main_RSS']
    shutdown = True

class tp4m(tp):
    """
    This is a smaller pageset (21 pages) of the updated web page test which
    was set to 100 pages from February 2009. It is designed for mobile
    Firefox and is a blend of regular and mobile friendly pages.
    """
    tpmanifest = '${talos}/page_load_test/tp4m.manifest'
    tpchrome = False
    rss = True
    tpcycles = 2
    win_counters = w7_counters = linux_counters = mac_counters = None
    remote_counters = ['Main_RSS']
    timeout = 1800

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
    tppagecycles = 1
    cycles = 1
    tpmozafterpaint = True
    tptimeout = 5000
    rss = True
    mainthread = True
    w7_counters = []
    win_counters = []
    linux_counters = []
    remote_counters = []
    mac_counters = []
    xperf_counters = ['main_startup_fileio', 'main_startup_netio', 'main_normal_fileio', 'main_normal_netio', 'nonmain_startup_fileio', 'nonmain_normal_fileio', 'nonmain_normal_netio', 'mainthread_readcount', 'mainthread_readbytes', 'mainthread_writecount', 'mainthread_writebytes']
    xperf_providers = ['PROC_THREAD', 'LOADER', 'HARD_FAULTS', 'FILENAME', 'FILE_IO', 'FILE_IO_INIT']
    xperf_user_providers = ['Mozilla Generic Provider', 'Microsoft-Windows-TCPIP']
    xperf_stackwalk = ['FileCreate', 'FileRead', 'FileWrite', 'FileFlush', 'FileClose']
    mobile = False # too many files to run, we will hit OOM
    filters = [["ignore_first", [1]], ['median', []]]
    timeout = 1800
    setup = '${talos}/xtalos/start_xperf.py ${talos}/bcontroller.yml'
    cleanup = '${talos}/xtalos/parse_xperf.py ${talos}/bcontroller.yml'
    preferences = {'extensions.autoDisableScopes': '',
                   'extensions.enabledScopes': '',
                   'talos.logfile': 'browser_output.txt'}


class tp5o(PageloaderTest):
    """
    Derived from the tp5n pageset, this is the 49 most reliable webpages.
    """
    tpcycles = 1
    tppagecycles = 25
    cycles = 1
    tpmozafterpaint = True
    tptimeout = 5000
    rss = True
    mainthread = False
    tpmanifest = '${talos}/page_load_test/tp5n/tp5o.manifest'
    win_counters = ['Main_RSS', 'Private Bytes', '% Processor Time']
    w7_counters = ['Main_RSS', 'Private Bytes', '% Processor Time', 'Modified Page List Bytes']
    linux_counters = ['Private Bytes', 'XRes', 'Main_RSS']
    mac_counters = ['Main_RSS']
    responsiveness = True
    sps_profile_interval = 2
    sps_profile_entries = 4000000
    mobile = False # too many files to run, we will hit OOM
    filters = [["ignore_first", [5]], ['median', []]]
    timeout = 1800

class tp5o_scroll(PageloaderTest):
    """
    Tests scroll (like tscrollx does, including ASAP) but on the tp5o pageset.
    """
    tpmanifest = '${talos}/page_load_test/tp5n/tp5o.manifest'
    tpcycles = 1
    tppagecycles = 12
    sps_profile_interval = 2
    sps_profile_entries = 2000000

    tpscrolltest = True
    """ASAP mode"""
    tpmozafterpaint = False
    preferences = {'layout.frame_rate': 0,
                   'docshell.event_starvation_delay_hint': 1,
                   'dom.send_after_paint_to_content': False}
    filters = [["ignore_first", [1]], ['median', []]]


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
    """ ASAP mode - keeping old pref (new is 0), since tsvg is being deprecated and we don't want to modify talos results for it now """
    preferences = {'layout.frame_rate': 10000}

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
    sps_profile_interval = 1
    sps_profile_entries = 1000000
    tpcycles = 1
    resolution = 20
    tpmozafterpaint = False
    preferences = {'dom.send_after_paint_to_content': False}

class kraken(PageloaderTest):
    """
    This is the Kraken javascript benchmark taken verbatim and slightly
    modified to fit into our pageloader extension and talos harness.
    """
    tpmanifest = '${talos}/page_load_test/kraken/kraken.manifest'
    tpcycles = 1
    tppagecycles = 1
    sps_profile_interval = 0.1
    sps_profile_entries = 1000000
    tpmozafterpaint = False
    preferences = {'dom.send_after_paint_to_content': False}
    filters = [['mean', []]]

class tcanvasmark(PageloaderTest):
    """
    CanvasMark benchmark v0.6
    """
    tpmanifest = '${talos}/page_load_test/canvasmark/canvasmark.manifest'
    win_counters = w7_counters = linux_counters = mac_counters = None
    remote_counters = None
    tpcycles = 5
    tppagecycles = 1
    timeout = 900
    sps_profile_interval = 10
    sps_profile_entries = 2500000
    tpmozafterpaint = False
    preferences = {'dom.send_after_paint_to_content': False}
    filters = [["ignore_first", [1]], ['median', []]]

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
    sps_profile_interval = 2
    sps_profile_entries = 10000000
    tpmanifest = '${talos}/page_load_test/dromaeo/css.manifest'

class dromaeo_dom(dromaeo):
    """
    Dromaeo suite of tests for JavaScript performance testing.
    See the Dromaeo wiki (https://wiki.mozilla.org/Dromaeo)
    for more information.

    Each page in the manifest is part of the dromaemo dom benchmark.
    """
    sps_profile_interval = 2
    sps_profile_entries = 10000000
    tpmanifest = '${talos}/page_load_test/dromaeo/dom.manifest'

class a11y(PageloaderTest):
    """
    This test ensures basic a11y tables and permutations do not cause
    performance regressions.
    """
    tpmanifest = '${talos}/page_load_test/a11y/a11y.manifest'
    tpmozafterpaint = True
    tpcycles = 5
    sps_profile_interval = 10
    sps_profile_entries = 300000
    mobile = False # we don't make a11y.manifest have urls, it just has dhtml.html instead of http://ip:port/dhtml.html
    filters = [["ignore_first", [1]], ['median', []]]

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

class tsvgx(tsvg):
    """
    Like the tsvg test this is an svg-only number that measures SVG
    rendering performance. Unlike tsvg, this test is row-based instead
    of column based.
    """
    tpmanifest = '${talos}/page_load_test/svgx/svgx.manifest'
    tpcycles = 1
    tppagecycles = 25
    tpmozafterpaint = False
    sps_profile_interval = 10
    sps_profile_entries = 1000000
    """ASAP mode"""
    preferences = {'layout.frame_rate': 0,
                   'docshell.event_starvation_delay_hint': 1,
                   'dom.send_after_paint_to_content': False}
    filters = [["ignore_first", [5]], ['median', []]]

class tsvgr_opacity(tsvg_opacity):
    """
    Like the tsvg_opacity test this is an svg-only number that measures SVG
    rendering performance. Unlike tsvg_opacity, this test is row-based
    instead of column based.
    """
    tpcycles = 1
    tppagecycles = 25
    sps_profile_interval = 1
    sps_profile_entries = 10000000
    filters = [["ignore_first", [5]], ['median', []]]

class tscrollr(PageloaderTest):
    """
    Like tscroll, this test does some scrolly thing. Unlike tscroll, this
    test is row-based instead of column based.
    """
    tpmanifest = '${talos}/page_load_test/scroll/scroll.manifest'
    tpcycles = 1
    tppagecycles = 25

class tscrollx(PageloaderTest):
    """
    Like tscroll, this test does some scrolly thing. Unlike tscroll, this
    test is row-based instead of column based.
    """
    tpmanifest = '${talos}/page_load_test/scroll/scroll.manifest'
    tpcycles = 1
    tppagecycles = 25
    tpmozafterpaint = False
    sps_profile_interval = 1
    sps_profile_entries = 1000000
    """ ASAP mode """
    preferences = {'layout.frame_rate': 0,
                   'docshell.event_starvation_delay_hint': 1,
                   'dom.send_after_paint_to_content': False}
    filters = [["ignore_first", [5]], ['median', []]]

class a11yr(PageloaderTest):
    """
    Like a11y, this test ensures basic a11y tables and permutations do not
    cause performance regressions. Unlike a11y, this test is row-based
    instead of column based.
    """
    tpmanifest = '${talos}/page_load_test/a11y/a11y.manifest'
    tpcycles = 1
    tppagecycles = 25
    tpmozafterpaint = True
    preferences = {'dom.send_after_paint_to_content': False}
    mobile = False # we don't make a11y.manifest have urls, it just has dhtml.html instead of http://ip:port/dhtml.html

# global test data
tests = [ts_paint, ts, tsvg, tdhtml, ts_paint_cold,
         tp4m, tp5n, tp5o, tpaint, tresize, tp5o_scroll,
         trobopan, tcheckerboard, tprovider, tcheck2, tcanvasmark,
         dromaeo_css, dromaeo_dom, v8_7, kraken, media_tests,
         tdhtmlr, tsvgr, tsvgr_opacity, tscrollr, a11yr,
         tsvgx, tscrollx, tart, cart, glterrain,
         sessionrestore, sessionrestore_no_auto_restore
         ]
test_dict = dict([(i.name(), i) for i in tests])
