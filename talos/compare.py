# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import json, urllib, httplib
import datetime, time
from optparse import OptionParser
import sys
import os
import filter

SERVER = 'graphs.mozilla.org'
selector = '/api/test/runs'
debug = 1

branch_map = {}
branch_map['Try']     = {'pgo':    {'id': 23, 'name': 'Try'},
                         'nonpgo': {'id': 113, 'name': 'Try'}}
branch_map['Firefox'] = {'pgo':    {'id': 1,  'name': 'Firefox'},
                         'nonpgo': {'id': 94, 'name': 'Firefox-Non-PGO'}}
branch_map['Inbound'] = {'pgo':    {'id': 63, 'name': 'Mozilla-Inbound'},
                         'nonpgo': {'id': 131, 'name': 'Mozilla-Inbound-Non-PGO'}}
branch_map['Cedar']   = {'pgo':    {'id': 26, 'name': 'Cedar'},
                         'nonpgo': {'id': 26, 'name': 'Cedar'}}
branch_map['UX']      = {'pgo':    {'id': 59, 'name': 'UX'},
                         'nonpgo': {'id': 137, 'name': 'UX-Non-PGO'}}
branches = ['Try', 'Firefox', 'Inbound', 'Cedar', 'UX']

# TODO: pull test names and reverse_tests from test.py in the future
# TODO: add android test names
test_map = {}
test_map['dromaeo_css'] = {'id': 72, 'tbplname': 'dromaeo_css'}
test_map['dromaeo_dom'] = {'id': 73, 'tbplname': 'dromaeo_dom'}
test_map['kraken'] = {'id': 232, 'tbplname': 'kraken'}
test_map['v8_7'] = {'id': 230, 'tbplname': 'v8_7'}
test_map['tscrollr'] = {'id': 222, 'tbplname': 'tscrollr_paint'}
test_map['a11yr'] = {'id': 223, 'tbplname': 'a11yr_paint'}
test_map['ts_paint'] = {'id': 83, 'tbplname': 'ts_paint'}
test_map['tpaint'] = {'id': 82, 'tbplname': 'tpaint'}
test_map['tsvgr'] = {'id': 224, 'tbplname': 'tsvgr'}
test_map['tsvgr_opacity'] = {'id': 225, 'tbplname': 'tsvgr_opacity'}
test_map['tresize'] = {'id': 254, 'tbplname': 'tresize'}
test_map['tp5n'] = {'id': 206, 'tbplname': 'tp5n_paint'}
test_map['tp5o'] = {'id': 255, 'tbplname': 'tp5o_paint'}
test_map['tp5o_scroll'] = {'id': 323, 'tbplname': 'tp5o_scroll'}
test_map['tsvgx'] = {'id': 281, 'tbplname': 'tsvgx'}
test_map['tscrollx'] = {'id': 287, 'tbplname': 'tscrollx_paint'}
test_map['sessionrestore'] = {'id': 313, 'tbplname':'sessionrestore'}
test_map['sessionrestore_no_auto_restore'] = {'id': 315, 'tbplname':'sessionrestore_no_auto_restore'}
test_map['tart'] = {'id': 293, 'tbplname': 'tart'}
test_map['cart'] = {'id': 309, 'tbplname': 'cart'}
test_map['tcanvasmark'] = {'id': 297, 'tbplname': 'tcanvasmark_paint'}
test_map['glterrain'] = {'id': 325, 'tbplname': 'glterrain'}
test_map['media_tests'] = {'id': 317, 'tbplname': 'media_tests'}

tests = ['tresize', 'kraken', 'v8_7', 'dromaeo_css', 'dromaeo_dom', 'a11yr', 'ts_paint', 'tpaint', 'tsvgr_opacity', 'tp5n', 'tp5o', 'tart', 'tcanvasmark', 'tsvgx', 'tscrollx', 'sessionrestore', 'sessionrestore_no_auto_restore', 'glterrain', 'cart', 'tp5o_scroll', 'media_tests' ]

reverse_tests = ['dromaeo_css', 'dromaeo_dom', 'v8', 'canvasmark']

platform_map = {}
platform_map['Linux'] = 33 #14 - 14 is the old fedora, we are now on Ubuntu slaves
platform_map['Linux (e10s)'] = 41
platform_map['Linux64'] = 35 #15 - 15 is the old fedora, we are now on Ubuntu slaves
platform_map['Linux64 (e10s)'] = 43
platform_map['Win7'] = 25 # 12 is for non-ix
platform_map['Win7 (e10s)'] = 47
platform_map['Win8'] = 31
platform_map['Win8 (e10s)'] = 49
platform_map['WinXP'] = 37 # 1 is for non-ix
platform_map['WinXP (e10s)'] = 45
platform_map['Win64'] = 19
platform_map['OSX64'] = 21 #10.6
platform_map['OSX64 (e10s)'] = 51
platform_map['OSX'] = 13 #10.5.8
platform_map['OSX10.8'] = 24
platform_map['OSX10.8 (e10s)'] = 53
platforms = ['Linux', 'Linux64', 'Win7', 'WinXP', 'Win8', 'OSX64', 'OSX10.8']
platforms_e10s = ['Linux (e10s)', 'Linux64 (e10s)', 'Win7 (e10s)', 'WinXP (e10s)', 'Win8 (e10s)', 'OSX64 (e10s)', 'OSX10.8 (e10s)']

# e10s is a new platform we are supporting, as we don't run it often there is not a need for it, right now it is just noise
# having it defined allows us to start looking at e10s vs non e10s.  How to do that with compare.py is not implemented, but now we can at least
# compare a try run with e10s data to m-c
platforms.extend(platforms_e10s)

def getGraphData(testid, branchid, platformid):
    body = {"id": testid, "branchid": branchid, "platformid": platformid}
    if debug >= 3:
        print "Querying graph server for: %s" % body
    params = urllib.urlencode(body)
    headers = {"Content-type": "application/x-www-form-urlencoded", "Accept": "text/plain"}
    conn = httplib.HTTPConnection(SERVER)
    conn.request("POST", selector, params, headers)
    response = conn.getresponse()
    data = response.read()

    if data:
        try:
            data = json.loads(data)
        except:
            print "NOT JSON: %s" % data
            return None

    if data['stat'] == 'fail':
        return None
    return data

# TODO: consider moving this to mozinfo or datazilla_client
def getDatazillaPlatform(os, platform, osversion, product):
    platform = None
    if product == 'Fennec':
        platform = 'Tegra'

    if os == 'linux':
        if platform == 'x86_64':
            platform = 'Linux64'
        else:
            platform = 'Linux'
    elif os == 'win':
        if osversion == '6.1.7600' or osversion == '6.1.7601':
            platform = 'Win'
        elif osversion == '6.2.9200':
            platform = 'Win8'
        elif osversion == '6.2.9200.m':
            platform = 'Win8.m'
        else:
            platform = 'WinXP'
    elif os == 'mac':
        if osversion.startswith('OS X 10.6'):
            platform = 'OSX64'
        elif osversion.startswith('OS X 10.8'):
            platform = 'OSX10.8'
    return platform


#TODO: move this to datazilla_client.
def getDatazillaCSET(revision, branchid):
    testdata = {}
    pgodata = {}
    xperfdata = {}
    cached = "%s.json" % revision
    if os.path.exists(cached):
        response = open(cached, 'r')
    else:
        conn = httplib.HTTPSConnection('datazilla.mozilla.org')
        cset = "/talos/testdata/raw/%s/%s" % (branchid, revision)
        conn.request("GET", cset)
        response = conn.getresponse()

    data = response.read()
    response.close()
    cdata = json.loads(data)

    for testrun in cdata:
        values = []
        platform = getDatazillaPlatform(testrun['test_machine']['os'],
                                        testrun['test_machine']['platform'],
                                        testrun['test_machine']['osversion'],
                                        testrun['test_build']['name'])

        if platform not in testdata:
            testdata[platform] = {}

        if platform not in pgodata:
            pgodata[platform] = {}

        pgo = True
        if 'Non-PGO' in testrun['test_build']['branch']:
            pgo = False

        suite = testrun['testrun']['suite']
        extension = ''
        if not testrun['testrun']['options']['tpchrome']:
            extension = "%s_nochrome" % extension

        # these test names are reported without _paint
        if 'svg' not in suite and \
           'kraken' not in suite and \
           'sunspider' not in suite and \
           'dromaeo' not in suite and \
           testrun['testrun']['options']['tpmozafterpaint']:
            if 'paint' not in suite: # handle tspaint_places_generated_*
                extension = "%s_paint" % extension

        suite = "%s%s" % (suite, extension)

        # This is a hack that means we are running xperf since tp5n was replaced by tp5o
        if platform == "Win" and suite == "tp5n_paint":
            xperfdata = testrun['results_xperf']

        for page in testrun['results']:

            index = 0
            if len(testrun['results'][page]) > 0:
                index = 0

            vals = sorted(testrun['results'][page][index:])[:-1]

            if len(vals) == 0:
                vals = [0]
            values.append(float(sum(vals))/len(vals))

        # ignore max
        if len(values) >= 2:
            values = sorted(values)[:-1]
        if len(values) == 0:
            values = [0]

        # mean
        if pgo:
            pgodata[platform][suite] = float(sum(values)/len(values))
            if debug > 1:
                print "%s: %s: %s (PGO)" % (platform, suite, pgodata[platform][suite])
        else:
            testdata[platform][suite] = float(sum(values)/len(values))
            if debug > 1:
                print "%s: %s: %s" % (platform, suite, testdata[platform][suite])

    return testdata, pgodata, xperfdata

def getDatazillaData(branchid):
    # TODO: resolve date, currently days_ago=7,

    # https://datazilla.mozilla.org/refdata/pushlog/list/?days_ago=7&branches=Mozilla-Inbound
    conn = httplib.HTTPSConnection('datazilla.mozilla.org')
    cset = "/refdata/pushlog/list/?days_ago=14&branches=%s" % branchid
    conn.request("GET", cset)
    response = conn.getresponse()
    data = response.read()
    jdata = json.loads(data)
    alldata = {}

    for item in jdata:
        alldata[jdata[item]['revisions'][0]] = getDatazillaCSET(jdata[item]['revisions'][0], branchid)
    return alldata

def parseGraphResultsByDate(data, start, end):
    low = sys.maxint
    high = 0
    count = 0
    runs = data['test_runs']
    vals = []
    for run in runs:
        if run[2] >= start and run[2] <= end:
            vals.append(run[3])
            if run[3] < low:
                low = run[3]
            if run[3] > high:
                high = run[3]
            count += 1

    average = 0
    geomean = 0
    if count > 0:
        average = filter.mean(vals)
        geomean = filter.geometric_mean(vals)
    return {'low': low, 'high': high, 'avg': average, 'geomean': geomean, 'count': count, 'data': vals}

def parseGraphResultsByChangeset(data, changeset):
    low = sys.maxint
    high = 0
    count = 0
    runs = data['test_runs']
    vals = []
    for run in runs:
        push = run[1]
        cset = push[2]
        if cset == changeset:
            vals.append(run[3])
            if run[3] < low:
                low = run[3]
            if run[3] > high:
                high = run[3]
            count += 1

    average = 0
    geomean = 0
    if count > 0:
        average = filter.mean(vals)
        geomean = filter.geometric_mean(vals)
    return {'low': low, 'high': high, 'avg': average, 'geomean': geomean, 'count': count, 'data': vals}


def compareResults(revision, branch, masterbranch, skipdays, history, platforms, tests, pgo=False, printurl=False, dzdata=None, pgodzdata=None, doPrint=False):
    startdate = int(time.mktime((datetime.datetime.now() - datetime.timedelta(days=(skipdays+history))).timetuple()))
    enddate = int(time.mktime((datetime.datetime.now() - datetime.timedelta(days=skipdays)).timetuple()))

    if doPrint:
        print "   test\t\t\tmin.\t->\tmax.\trev."

    for p in platforms:
        output = ["%s:\n" % p]

        for t in tests:
            dzval = None
            if dzdata:
                if p in dzdata:
                    if test_map[t]['tbplname'] in dzdata[p]:
                        dzval = dzdata[p][test_map[t]['tbplname']]

            pgodzval = None
            if pgodzdata:
                if p in pgodzdata:
                    if test_map[t]['tbplname'] in pgodzdata[p]:
                        pgodzval = pgodzdata[p][test_map[t]['tbplname']]

            test_bid = branch_map[branch]['nonpgo']['id']
            if p.startswith('OSX') or pgo:
                test_bid = branch_map[branch]['pgo']['id']

            bid = branch_map[masterbranch]['nonpgo']['id']
            if p.startswith('OSX') or pgo:
                bid = branch_map[masterbranch]['pgo']['id']

            data = getGraphData(test_map[t]['id'], bid, platform_map[p])
            testdata = getGraphData(test_map[t]['id'], test_bid, platform_map[p])
            if data and testdata:
                results = parseGraphResultsByDate(data, startdate, enddate)
                test = parseGraphResultsByChangeset(testdata, revision)
                status = ''
                if test['geomean'] < results['low']:
                    status = ':)'
                    if t in reverse_tests:
                        status = ':('
                if test['geomean'] > results['high']:
                    status = ':('
                    if t in reverse_tests:
                        status = ':)'

                if test['low'] == sys.maxint or results['low'] == sys.maxint or \
                   test['high'] == 0  or results['high'] == 0:
                    output.append("   %-18s\tNo results found" % t)
                else:
                    string = "%2s %-18s\t%7.1f\t->\t%7.1f\t%7.1f" % (status, t, results['low'], results['high'], test['avg'])
                    if dzval and pgodzval:
                        string = "\t[%s] [PGO: %s]" % (dzval, pgodzval)
                    if printurl:
                        url = shorten("http://graphs.mozilla.org/graph.html#tests=[[%s,%s,%s]]" % (test_map[t]['id'], bid, platform_map[p]))
                        string = "\t%s" % url
                    output.append(string)
            else:
                output.append("   %-18s\tNo data for platform" % t)

        if doPrint:
            print '\n'.join(output)

class CompareOptions(OptionParser):

    def __init__(self):
        OptionParser.__init__(self)

        self.add_option("--revision",
                        action = "store", type = "string", dest = "revision",
                        default = None,
                        help = "revision of the source you are testing")

        self.add_option("--branch",
                        action = "store", type = "string", dest = "branch",
                        default = "Try",
                        help = "branch that your revision landed on which you are testing, default 'Try'.  Options are: %s" % (branches))

        self.add_option("--masterbranch",
                        action = "store", type = "string", dest = "masterbranch",
                        default = "Firefox",
                        help = "master branch that you will be comparing against, default 'Firefox'.  Options are: %s" % (branches))

        self.add_option("--skipdays",
                        action = "store", type = "int", dest = "skipdays",
                        default = 0,
                        help = "Specify the number of days to ignore results, default '0'.  Note: If a regression landed 4 days ago, use --skipdays=5")

        self.add_option("--history",
                        action = "store", type = "int", dest = "history",
                        default = 14,
                        help = "Specify the number of days in history to go back and get results.  If specified in conjunction with --skipdays, we will collect <history> days starting an extra <skipdays> in the past.  For example, if you have skipdays as 7 and history as 14, then we will collect data from 7-21 days in the past.  Default is 14 days")

        self.add_option("--platform",
                        action = "append", type = "choice", dest = "platforms",
                        default = None, choices = platforms,
                        help = "Specify a single platform to compare. This option can be specified multiple times and defaults to 'All' if not specified.  Options are: %s" % (platforms))

        self.add_option("--testname",
                        action = "append", type = "choice", dest = "testnames",
                        default = None, choices = tests,
                        help = "Specify a single test to compare. This option can be specified multiple times and defaults to 'All' if not specified. Options are: %s" % (tests))

        self.add_option("--print-graph-url",
                        action = "store_true", dest = "printurl",
                        default = False,
                        help = "Print a url that can link to the data in graph server")

        self.add_option("--pgo",
                        action = "store_true", dest = "pgo",
                        default = False,
                        help = "Use PGO Branch if available")

        self.add_option("--xperf",
                        action = "store_true", dest = "xperf",
                        default = False,
                        help = "Print xperf information")

def main():
    global platforms, tests
    parser = CompareOptions()
    options, args = parser.parse_args()

    if options.platforms:
        platforms = options.platforms

    if options.testnames:
        tests = options.testnames

    if options.masterbranch and not options.masterbranch in branches:
        parser.error("ERROR: the masterbranch '%s' you specified does not exist in '%s'" % (options.masterbranch, branches))

    branch = None
    if options.branch in branches:
        branch = branch_map[options.branch]['nonpgo']['name']
        if options.pgo:
            branch = branch_map[options.branch]['pgo']['name']
    else:
        parser.error("ERROR: the branch '%s' you specified does not exist in '%s'" % (options.branch, branches))

    if options.skipdays:
        if options.skipdays > 30:
            parser.error("ERROR: please specify the skipdays between 0-30")

    if not options.revision:
        parser.error("ERROR: --revision is required")

    #TODO: We need to ensure we have full coverage of the pushlog before we can do this.
#    alldata = getDatazillaData(options.branch)
#    datazilla, pgodatazilla, xperfdata = alldata[options.revision]
    datazilla, pgodatazilla, xperfdata = getDatazillaCSET(options.revision, branch)
    if options.xperf:
        print xperfdata
    else:
        compareResults(options.revision, options.branch, options.masterbranch, options.skipdays, options.history, platforms, tests, options.pgo, options.printurl, datazilla, pgodatazilla, True)

def shorten(url):
    headers = {'content-type':'application/json'}
    base_url = "www.googleapis.com"

    conn = httplib.HTTPSConnection(base_url)
    body = json.dumps(dict(longUrl=url))

    conn.request("POST", "/urlshortener/v1/url", body, headers)
    resp = conn.getresponse()
    if resp.reason == "OK":
        data = resp.read()
        shortened = json.loads(data)
        if 'id' in shortened:
            return shortened['id']
    return url

if __name__ == "__main__":
    main()
