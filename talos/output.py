# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""output formats for Talos"""

import filter
import imp
import mozinfo
import os
import post_file
import time
import urllib
import urlparse
import utils
from StringIO import StringIO
from dzclient import DatazillaRequest, DatazillaResult, DatazillaResultsCollection

try:
    import json
except ImportError:
    import simplejson as json

def filesizeformat(bytes):
    """
    Format the value like a 'human-readable' file size (i.e. 13 KB, 4.1 MB, 102
    bytes, etc).
    """
    bytes = float(bytes)
    formats = ('B', 'KB', 'MB')
    for f in formats:
        if bytes < 1024:
            return "%.1f%s" % (bytes, f)
        bytes /= 1024
    return "%.1fGB" % bytes #has to be GB

class Output(object):
    """abstract base class for Talos output"""

    @classmethod
    def check(cls, urls, **options):
        """check to ensure that the urls are valid"""

    def __init__(self, results):
        """
        - results : TalosResults instance
        """
        self.results = results

    def __call__(self):
        """return list of results strings"""
        raise NotImplementedError("Abstract base class")

    def output(self, results, results_url):
        """output to the results_url
        - results_url : http:// or file:// URL
        - results : list of results
        """

        # parse the results url
        results_url_split = urlparse.urlsplit(results_url)
        results_scheme, results_server, results_path, _, _ = results_url_split

        if results_scheme in ('http', 'https'):
            self.post(results, results_server, results_path, results_scheme)
        elif results_scheme == 'file':
            try:
                f = file(results_path, 'w')
                for result in results:
                    f.write("%s\n" % result)
                f.close()
            except Exception, e:
                print "Exception in writing file '%s' from results_url: %s" % (results_path, results_url)
                raise
        else:
            raise NotImplementedError("%s: %s - only http://, https://, and file:// supported" % (self.__class__.__name__, results_url))

    def post(self, results, server, path, scheme):
        raise NotImplementedError("Abstract base class")

    @classmethod
    def shortName(cls, name):
        """short name for counters"""
        names = {"Working Set": "memset",
                 "% Processor Time": "%cpu",
                 "Private Bytes": "pbytes",
                 "RSS": "rss",
                 "XRes": "xres",
                 "Modified Page List Bytes": "modlistbytes",
                 "Main_RSS": "main_rss",
                 "Content_RSS": "content_rss"}
        return names.get(name, name)

    @classmethod
    def isMemoryMetric(cls, resultName):
        """returns if the result is a memory metric"""
        memory_metric = ['memset', 'rss', 'pbytes', 'xres', 'modlistbytes', 'main_rss', 'content_rss'] #measured in bytes
        return bool([i for i in memory_metric if i in resultName])

    @classmethod
    def responsiveness_Metric(cls, val_list):
        return round(sum([int(x)*int(x) / 1000000.0 for x in val_list]))

    @classmethod
    def v8_Metric(cls, val_list):
        """v8 benchmark score"""
        reference = {'Crypto': 266181.,
                     'DeltaBlue': 66118.,
                     'EarlyBoyer': 666463.,
                     'NavierStokes': 1484000.,
                     'RayTrace': 739989.,
                     'RegExp': 910985.,
                     'Richards': 35302.,
                     'Splay': 81491.
                     }
        tests = [('Crypto', ['Encrypt', 'Decrypt']),
                 ('DeltaBlue', ['DeltaBlue']),
                 ('EarlyBoyer', ['Earley', 'Boyer']),
                 ('NavierStokes', ['NavierStokes']),
                 ('RayTrace', ['RayTrace']),
                 ('RegExp', ['RegExp']),
                 ('Richards', ['Richards']),
                 ('Splay', ['Splay'])]
        results = dict([(j, i) for i, j in val_list])
        scores = []
        utils.noisy("v8 benchmark")
        for test, benchmarks in tests:
            vals = [results[benchmark] for benchmark in benchmarks]
            mean = filter.geometric_mean(vals)
            score = reference[test] / mean
            scores.append(score)
            utils.noisy(" %s: %s" % (test, score * 100))
        score =  100 * filter.geometric_mean(scores)
        utils.noisy("Score: %s" % score)
        return score

    @classmethod
    def JS_Metric(cls, val_list):
        """v8 benchmark score"""
        results = [i for i, j in val_list]
        utils.noisy("javascript benchmark")
        return sum(results)

class GraphserverOutput(Output):

    retries = 5   # number of times to attempt to contact graphserver
    info_format = ['title', 'testname', 'branch_name', 'sourcestamp', 'buildid', 'date']

    @classmethod
    def check(cls, urls):
        # ensure results_url link exists
        post_file.test_links(*urls)

    def __call__(self):
        """
        results to send to graphserver:
        construct all the strings of data, one string per test and one string  per counter
        """

        result_strings = []

        info_dict = dict(title=self.results.title,
                         date=self.results.date,
                         branch_name=self.results.browser_config['branch_name'],
                         sourcestamp=self.results.browser_config['sourcestamp'],
                         buildid=self.results.browser_config['buildid'],
                         browser_name=self.results.browser_config['browser_name'],
                         browser_version=self.results.browser_config['browser_version']
                         )

        for test in self.results.results:

            utils.debug("Working with test: %s" % test.name())


            # get full name of test
            testname = test.name()
            if test.format == 'tpformat':
                # for some reason, we append the test extension to tp results but not ts
                # http://hg.mozilla.org/build/talos/file/170c100911b6/talos/run_tests.py#l176
                testname += self.results.test_name_extension

            utils.stamped_msg("Generating results file: %s" % test.name(), "Started")

            # HACK: when running xperf, we upload xperf counters to the graph server but we do not want to
            # upload the test results as they will confuse the graph server
            if not test.using_xperf:
                vals = []
                for result in test.results:
                    # per test filters
                    _filters = self.results.filters
                    if 'filters' in test.test_config:
                        try:
                            _filters = filter.filters_args(test.test_config['filters'])
                        except AssertionError, e:
                            raise utils.talosError(str(e))

                    vals.extend(result.values(_filters))
                result_strings.append(self.construct_results(vals, testname=testname, **info_dict))
                utils.stamped_msg("Generating results file: %s" % test.name(), "Stopped")

            # counter results
            for cd in test.all_counter_results:
                for counter_type, values in cd.items():
                    # get the counter name
                    counterName = '%s_%s' % (test.name() , self.shortName(counter_type))
                    if not values:
                        # failed to collect any data for this counter
                        utils.stamped_msg("No results collected for: " + counterName, "Error")
                        continue

                    # counter values
                    vals = [[x, 'NULL'] for x in values]

                    # append test name extension but only for tpformat tests
                    if test.format == 'tpformat':
                        counterName += self.results.test_name_extension

                    info = info_dict.copy()
                    info['testname'] = counterName

                    # append the counter string
                    utils.stamped_msg("Generating results file: %s" % counterName, "Started")
                    result_strings.append(self.construct_results(vals, **info))
                    utils.stamped_msg("Generating results file: %s" % counterName, "Stopped")

        return result_strings

    def responsiveness_test(self, testname):
        """returns if the test is a responsiveness test"""
        # XXX currently this just looks for the string
        # 'responsiveness' in the test name.
        # It would be nice to be more declarative about this
        return 'responsiveness' in testname

    def construct_results(self, vals, testname, **info):
        """
        return results string appropriate to graphserver
        - vals: list of 2-tuples: [(val, page)
        - kwargs: info necessary for self.info_format interpolation
        see https://wiki.mozilla.org/Buildbot/Talos/DataFormat
        """

        info['testname'] = testname
        info_format = self.info_format
        responsiveness = self.responsiveness_test(testname)
        _type = 'VALUES'
        average = None
        if responsiveness:
            _type = 'AVERAGE'
            average = self.responsiveness_Metric([val for (val, page) in vals])
        elif testname.startswith('v8_7'):
            _type = 'AVERAGE'
            average = self.v8_Metric(vals)
        elif testname.startswith('sunspider') or testname.startswith('kraken'):
            _type = 'AVERAGE'
            average = self.JS_Metric(vals)

        # ensure that we have all of the info data available
        missing = [i for i in info_format if i not in info]
        if missing:
            raise utils.talosError("Missing keys: %s" % missing)
        info = ','.join([str(info[key]) for key in info_format])

        # write the data
        buffer = StringIO()
        buffer.write("START\n")
        buffer.write("%s\n" % _type)
        buffer.write('%s\n' % info)
        if average is not None:
            # write some kind of average
            buffer.write("%s\n" % average)
        else:
            for i, (val, page) in enumerate(vals):
                buffer.write("%d,%.2f,%s\n" % (i,float(val), page))
        buffer.write("END")
        return buffer.getvalue()

    def process_Request(self, post):
        """get links from the graphserver response"""
        links = ""
        lines = post.split('\n')
        for line in lines:
            if line.find("RETURN\t") > -1:
                line = line.replace("RETURN\t", "")
                links +=  line+ '\n'
            utils.debug("process_Request line: %s" % line)
        if not links:
            raise utils.talosError("send failed, graph server says:\n%s" % post)
        return links

    def post(self, results, server, path, scheme):
        """post results to the graphserver"""

        links = ''
        wait_time = 5 # number of seconds between each attempt

        for index, data_string in enumerate(results):

            times = 0
            msg = ""
            while times < self.retries:
                utils.noisy("Posting result %d of %d to %s://%s%s, attempt %d" % (index, len(results), scheme, server, path, times))
                try:
                    links += self.process_Request(post_file.post_multipart(server, path, files=[("filename", "data_string", data_string)]))
                    break
                except utils.talosError, e:
                    msg = e.msg
                except Exception, e:
                    msg = str(e)
                times += 1
                time.sleep(wait_time)
                wait_time *= 2
            else:
                raise utils.talosError("Graph server unreachable (%d attempts)\n%s" % (self.retries, msg))

        if not links:
            # you're done
            return links
        lines = links.split('\n')

        # print graph results
        self.results_from_graph(lines, server)

        # return links from graphserver
        return links

    def results_from_graph(self, lines, results_server):
        """print results from graphserver POST submission"""
        # TODO: document what response is actually supposed to look like

        url_format = "http://%s/%s"
        link_format= "<a href=\'%s\'>%s</a>"
        first_results = 'RETURN:<br>'
        last_results = ''
        full_results = '\nRETURN:<p style="font-size:smaller;">Details:<br>'

        for line in lines:
            if not line:
                continue
            linkvalue = -1
            linkdetail = ""
            values = line.split("\t")
            linkName = values[0]
            if len(values) == 2:
                linkdetail = values[1]
            else:
                linkvalue = float(values[1])
                linkdetail = values[2]
            if linkvalue > -1:
                if self.isMemoryMetric(linkName):
                    linkName += ": " + filesizeformat(linkvalue)
                else:
                    linkName += ": %s" % linkvalue
                url = url_format % (results_server, linkdetail)
                link = link_format % (url, linkName)
                first_results = first_results + "\nRETURN:" + link + "<br>"
            else:
                url = url_format % (results_server, linkdetail)
                link = link_format % (url, linkName)
                last_results = last_results + '| ' + link + ' '
        full_results = first_results + full_results + last_results + '|</p>'
        print full_results


class DatazillaOutput(Output):
    """send output to datazilla"""

    def __init__(self, results, authfile=None):
        Output.__init__(self, results)
        self.authfile = authfile
        self.oauth = None
        if authfile is not None:
            # get datazilla oauth credentials
            assert os.path.exists(authfile), "Auth file not found: %s" % authfile
            module_name = 'passwords'
            module = imp.load_source(module_name, authfile)
            self.oauth = getattr(module, 'datazillaAuth', None)
            if self.oauth is None:
                utils.noisy("File '%s' does not contain datazilla oauth information" % authfile)

    def output(self, results, results_url):
        """output to the results_url
        - results : DatazillaResults instance
        - results_url : http:// or file:// URL
        """

        # print out where we're sending
        utils.noisy("Outputting datazilla results to %s" % results_url)

        # parse the results url
        results_url_split = urlparse.urlsplit(results_url)
        results_scheme, results_server, results_path, _, _ = results_url_split

        if results_scheme in ('http', 'https'):
            self.post(results, results_server, results_path, results_scheme)
        elif results_scheme == 'file':
            f = file(results_path, 'w')
            f.write(json.dumps(results.datasets(), indent=2, sort_keys=True))
            f.close()
        else:
            raise NotImplementedError("%s: %s - only http://, https://, and file:// supported" % (self.__class__.__name__, results_url))

    def __call__(self):

        # platform
        machine = self.test_machine()

        # build information
        browser_config = self.results.browser_config

        # a place to put results
        res = DatazillaResult()

        for test in self.results.results:
            suite = "Talos %s" % test.name()
            res.add_testsuite(suite, options=self.run_options(test))

            # serialize test results
            results = {}
            if not test.using_xperf:
                for result in test.results:
                    # XXX this will not work for manifests which list
                    # the same page name twice. It also ignores cycles
                    for page, val in result.raw_values():
                        if page == 'NULL':
                            results.setdefault(test.name(), []).extend(val)
                        else:
                            results.setdefault(page, []).extend(val)
                    for result, values in results.items():
                        res.add_test_results(suite, result, values)

            # counters results_aux data
            for cd in test.all_counter_results:
                for name, vals in cd.items():
                    res.add_auxiliary_results(suite, name, vals)

        # make a datazilla test result collection
        collection = DatazillaResultsCollection(machine_name=machine['name'],
                                                os=machine['os'],
                                                os_version=machine['osversion'],
                                                platform=machine['platform'],
                                                build_name=browser_config['browser_name'],
                                                version=browser_config['browser_version'],
                                                revision=browser_config['sourcestamp'],
                                                branch=browser_config['branch_name'],
                                                id=browser_config['buildid'],
                                                test_date=self.results.date)
        collection.add_datazilla_result(res)
        return collection

    def post(self, results, server, path, scheme):
        """post the data to datazilla"""

        # datazilla project
        project = path.strip('/')

        # oauth credentials
        oauth_key = None
        oauth_secret = None
        if self.oauth:
            project_oauth = self.oauth.get(project)
            if project_oauth:
                required = ['oauthKey', 'oauthSecret']
                if set(required).issubset(project_oauth.keys()):
                    oauth_key = project_oauth['oauthKey']
                    oauth_secret = project_oauth['oauthSecret']
                else:
                    utils.noisy("%s not found for project '%s' in '%s' (found: %s)" % (required, project, self.authfile, project_oauth.keys()))
            else:
                utils.noisy("No oauth credentials found for project '%s' in '%s'" % (project, self.authfile))
        utils.noisy("datazilla: %s//%s/%s; oauth=%s" % (scheme, server, project, bool(oauth_key and oauth_secret)))

        # submit the request
        req = DatazillaRequest.create(scheme, server, project, oauth_key, oauth_secret, results)
        responses = req.submit()

        # print error responses
        for response in responses:
            if response.status != 200:
                print "Error posting to %s://%s/%s: %s %s" % (scheme, server, project, response.status, response.reason)

    def run_options(self, test):
        """test options for datazilla"""

        options = {}
        test_options = ['rss', 'tpchrome', 'tpmozafterpaint', 'tpcycles', 'tppagecycles', 'tprender', 'tpdelay', 'responsiveness', 'shutdown']
        for option in test_options:
            if option not in test.test_config:
                continue
            options[option] = test.test_config[option]
        if test.extensions is not None:
            options['extensions'] = [{'name': extension}
                                     for extension in test.extensions]
        return options

    def test_machine(self):
        """return test machine platform in a form appropriate to datazilla"""
        if self.results.remote:
            # TODO: figure out how to not hardcode this, specifically the version !!
            # should probably come from the agent (sut/adb) and passed in
            platform = "Android"
            version = "4.0.3"
            processor = "arm"
        else:
            platform = mozinfo.os
            version = mozinfo.version
            processor = mozinfo.processor

        return dict(name=self.results.title, os=platform, osversion=version, platform=processor)

# available output formats
formats = {'datazilla_urls': DatazillaOutput,
           'results_urls': GraphserverOutput}
