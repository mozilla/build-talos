# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import json, urllib, httplib
import datetime, time
from optparse import OptionParser
import sys

SERVER = 'graphs.mozilla.org'
selector = '/api/test/runs'
debug = 1

branch_map = {}
branch_map['Try'] = {'pgo': 23, 'nonpgo': 113}
branch_map['Firefox'] = {'pgo': 1, 'nonpgo': 94}
branch_map['Inbound'] = {'pgo': 63, 'nonpgo': 131}
branch_map['Cedar'] = {'pgo': 26, 'nonpgo': 26}
branches = ['Try', 'Firefox', 'Inbound', 'Cedar']

# TODO: pull test names and reverse_tests from test.py in the future
test_map = {}
test_map['tdhtmlr'] = {'id':220, 'tbplname': 'tdhtmlr_paint'}
test_map['tdhtmlr_nochrome'] = {'id': 221, 'tbplname': 'tdhtmlr_nochrome_paint'}
test_map['ts_places_med'] = {'id': 53, 'tbplname': 'ts_places_generated_med'}
test_map['ts_places_max'] = {'id': 54, 'tbplname': 'ts_places_generated_max'}
test_map['tspaint_places_med'] = {'id': 226, 'tbplname': 'tspaint_places_generated_med'}
test_map['tspaint_places_max'] = {'id': 227, 'tbplname': 'tspaint_places_generated_max'}
test_map['dromaeo_css'] = {'id': 72, 'tbplname': 'dromaeo_css'}
test_map['dromaeo_dom'] = {'id': 73, 'tbplname': 'dromaeo_dom'}
test_map['kraken'] = {'id': 232, 'tbplname': 'kraken'}
test_map['sunspider'] = {'id': 228, 'tbplname': 'sunspider'}
test_map['v8'] = {'id': 230, 'tbplname': 'v8_7'}
test_map['tscrollr'] = {'id': 222, 'tbplname': 'tscrollr_paint'}
test_map['a11yr'] = {'id': 223, 'tbplname': 'a11yr_paint'}
test_map['ts_paint'] = {'id': 83, 'tbplname': 'ts_paint'}
test_map['tpaint'] = {'id': 82, 'tbplname': 'tpaint'}
test_map['tsvgr'] = {'id': 224, 'tbplname': 'tsvgr'}
test_map['tsvgr_opacity'] = {'id': 225, 'tbplname': 'tsvgr_opacity'}
test_map['tresize'] = {'id': 254, 'tbplname': 'tresize'}
#tests['tp5r_paint'] = 139
test_map['tp5n'] = {'id': 206, 'tbplname': 'tp5n_paint'}
tests = ['tdhtmlr', 'tresize', 'tdhtmlr_nochrome', 'tspaint_places_med', 'tspaint_places_max', 'kraken', 'sunspider', 'v8', 'dromaeo_css', 'dromaeo_dom', 'tscrollr', 'a11yr', 'ts_paint', 'tpaint', 'tsvgr', 'tsvgr_opacity', 'tp5n']

reverse_tests = ['dromaeo_css', 'dromaeo_dom']

platform_map = {}
platform_map['Linux'] = 14
platform_map['Linux64'] = 15
platform_map['Win'] = 12
platform_map['WinXP'] = 1
platform_map['Win64'] = 19
platform_map['OSX10.7'] = 22
platform_map['OSX64'] = 21 #10.6
platform_map['OSX'] = 13 #10.5.8
platforms = ['Linux', 'Linux64', 'Win', 'WinXP', 'OSX10.7', 'OSX64', 'OSX'] #'Win64' doesn't have talos results

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

def parseGraphResultsByDate(data, start, end):
    low = sys.maxint
    high = 0
    count = 0
    runs = data['test_runs']
    for run in runs:
        if run[2] >= start and run[2] <= end:
            if run[3] < low:
                low = run[3]
            if run[3] > high:
                high = run[3]
            count += 1

    return {'low': low, 'high': high, 'count': count}

def parseGraphResultsByChangeset(data, changeset):
    low = sys.maxint
    high = 0
    count = 0
    runs = data['test_runs']
    for run in runs:
        push = run[1]
        cset = push[2]
        if cset == changeset:
            if run[3] < low:
                low = run[3]
            if run[3] > high:
                high = run[3]
            count += 1

    return {'low': low, 'high': high, 'count': count}


def compareResults(revision, branch, masterbranch, startdate, enddate, platforms, tests, printurl):
    for p in platforms:
        print "%s:" % (p)
        for t in tests:
            test_bid = branch_map[branch]['nonpgo']
            if p.startswith('OSX'):
                test_bid = branch_map[branch]['pgo']

            bid = branch_map[masterbranch]['nonpgo']
            if p.startswith('OSX'):
                bid = branch_map[masterbranch]['pgo']
        
            data = getGraphData(test_map[t]['id'], bid, platform_map[p])
            testdata = getGraphData(test_map[t]['id'], test_bid, platform_map[p])
            if data and testdata:
                results = parseGraphResultsByDate(data, startdate, enddate)
                test = parseGraphResultsByChangeset(testdata, revision)
                status = ''
                if test['low'] < results['low']:
                    status = ':) '
                    if t in reverse_tests:
                        status = ':( '
                if test['high'] > results['high']:
                    status = ':( '
                    if t in reverse_tests:
                        status = ':) '

                if test['low'] == sys.maxint or results['low'] == sys.maxint or \
                   test['high'] == 0  or results['high'] == 0:
                    print "    %s: No results found" % (t)

                else:
                    url = ""
                    if printurl:
                        url = shorten("http://graphs.mozilla.org/graph.html#tests=[[%s,%s,%s]]" % (test_map[t]['id'], bid, platform_map[p]))
                    print "    %s%s: %s -> %s; %s.  %s" % (status, t, results['low'], results['high'], test['low'], url)
            else:
                print "    %s: No data for platform" % t

class CompareOptions(OptionParser):

  def __init__(self):
    OptionParser.__init__(self)

    self.add_option("--revision",
                    action = "store", type = "string", dest = "revision",
                    default = None,
                    help = "revision of the source you are testing")

    self.add_option("--branch",
                    action = "store", type = "string", dest = "branch",
                    default = None,
                    help = "branch that your revision landed on which you are testing, default 'Try'.  Options are: %s" % (branches))

    self.add_option("--masterbranch",
                    action = "store", type = "string", dest = "masterbranch",
                    default = None,
                    help = "master branch that you will be comparing against, default 'Firefox'.  Options are: %s" % (branches))

    self.add_option("--skipdays",
                    action = "store", type = "int", dest = "skipdays",
                    default = 0,
                    help = "Specify the number of days to ignore results, default '0'.  Note: If a regression landed 4 days ago, use --skipdays=5")

    self.add_option("--platform",
                    action = "store", type = "string", dest = "platform",
                    default = None,
                    help = "Specify a single platform to compare, default 'All'.  Options are: %s" % (platforms))

    self.add_option("--testname",
                    action = "store", type = "string", dest = "testname",
                    default = None,
                    help = "Specify a single test to compare, default 'All'.  Options are: %s" % (tests))

    self.add_option("--print-graph-url",
                    action = "store_true", dest = "printurl",
                    default = False,
                    help = "Print a url that can link to the data in graph server")

def main():
    global platforms, tests
    parser = CompareOptions()
    options, args = parser.parse_args()

    if options.platform:
        if options.platform in platforms:
            platforms = [options.platform]
        else:
            parser.error("ERROR: the platform '%s' you specified does not exist in '%s'" % (options.platform, platforms))

    if options.testname:
        if options.testname in tests:
            tests = [options.testname]
        else:
            parser.error("ERROR: the testname '%s' you specified does not exist in '%s'" % (options.testname, tests))

    masterbranch = 'Firefox'
    if options.masterbranch:
        if options.masterbranch in branches:
            masterbranch = options.masterbranch
        else:
            parser.error("ERROR: the masterbranch '%s' you specified does not exist in '%s'" % (options.masterbranch, branches))

    branch = 'Try'
    if options.branch:
        if options.branch in branches:
            branch = options.branch
        else:
            parser.error("ERROR: the branch '%s' you specified does not exist in '%s'" % (options.branch, branches))

    if options.skipdays:
        if options.skipdays > 30:
            parser.error("ERROR: please specify the skipdays between 0-30")

    if not options.revision:
        parser.error("ERROR: --revision is required")

    startdate = int(time.mktime((datetime.datetime.now() - datetime.timedelta(days=(options.skipdays+14))).timetuple()))
    enddate = int(time.mktime((datetime.datetime.now() - datetime.timedelta(days=options.skipdays)).timetuple()))

    compareResults(options.revision, branch, masterbranch, startdate, enddate, platforms, tests, options.printurl)

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


