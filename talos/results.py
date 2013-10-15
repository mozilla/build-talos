#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
objects and methods for parsing and serializing Talos results
see https://wiki.mozilla.org/Buildbot/Talos/DataFormat
"""

import filter
import optparse
import os
import output
import re
import sys
import time
import utils
import csv

try:
    import json
except ImportError:
    import simplejson as json

__all__ = ['TalosResults', 'TestResults', 'TsResults', 'PageloaderResults', 'BrowserLogResults', 'main']

class TalosResults(object):
    """Container class for Talos results"""

    def __init__(self, title, date, browser_config, filters, remote=False, test_name_extension=''):
        self.results = []
        self.filters = filters
        self.test_name_extension = test_name_extension
        self.remote = remote

        # info needed for graphserver
        self.title = title
        self.date = date
        self.browser_config = browser_config

    def add(self, test_results):
        self.results.append(test_results)

    def check_output_formats(self, output_formats, **output_options):
        """check output formats"""

        # ensure formats are available
        formats = output_formats.keys()
        missing = self.check_formats_exist(formats)
        if missing:
            raise utils.talosError("Output format(s) unknown: %s" % ','.join(missing))

        # perform per-format check
        for format, urls in output_formats.items():
            cls = output.formats[format]
            cls.check(urls, **(output_options.get(format, {})))

    @classmethod
    def check_formats_exist(cls, formats):
        """
        ensure that all formats are registered
        return missing formats
        """
        return [i for i in formats if i not in output.formats]

    def output(self, output_formats, **output_options):
        """
        output all results to appropriate URLs
        - output_formats: a dict mapping formats to a list of URLs
        - output_options: a dict mapping formats to options for each format
        """

        utils.info("Outputting talos results => %s", output_formats)
        tbpl_output = {}
        try:

            for key, urls in output_formats.items():
                options = output_options.get(key, {})
                _output = output.formats[key](self, **options)
                results = _output()
                for url in urls:
                    _output.output(results, url, tbpl_output)

        except utils.talosError, e:
            # print to results.out
            try:
                _output = output.GraphserverOutput(self)
                results = _output()
                _output.output('file://%s' % os.path.join(os.getcwd(), 'results.out'), results)
            except:
                pass
            print '\nFAIL: %s' % e.msg.replace('\n', '\nRETURN:')
            raise e

        print "TinderboxPrint: TalosResult: %s" % json.dumps(tbpl_output)


class TestResults(object):
    """container object for all test results across cycles"""

    def __init__(self, test_config, global_counters=None, extensions=None):
        self.results = []
        self.test_config = test_config
        self.format = None
        self.global_counters = global_counters or {}
        self.all_counter_results = []
        self.extensions = extensions
        self.using_xperf = False

    def name(self):
        return self.test_config['name']

    def add(self, results, counter_results=None):
        """
        accumulate one cycle of results
        - results : TalosResults instance or path to browser log
        - counter_results : counters accumulated for this cycle
        """

        if isinstance(results, basestring):
            # ensure the browser log exists
            if not os.path.isfile(results):
                raise talosError("no output from browser [%s]" % results)

            # convert to a results class via parsing the browser log
            browserLog = BrowserLogResults(filename=results, counter_results=counter_results, global_counters=self.global_counters)
            results = browserLog.results()

        self.using_xperf = browserLog.using_xperf
        # ensure the results format matches previous results
        if self.results:
            if not results.format == self.results[0].format:
                raise utils.talosError("Conflicting formats for results")
        else:
            self.format = results.format

        self.results.append(results)

        if counter_results:
            self.all_counter_results.append(counter_results)

class Results(object):
    def filter(self, *filters):
        """
        filter the results set;
        applies each of the filters in order to the results data
        filters should be callables that take a list
        the last filter should return a scalar (float or int)
        returns a list of [[data, page], ...]
        """
        retval = []
        for result in self.results:
            page = result['page']
            data = result['runs']
            data = filter.apply(data, filters)
            retval.append([data, page])
        return retval

    def raw_values(self):
        return [(result['page'], result['runs']) for result in self.results]

    def values(self, filters):
        """return filtered (value, page) for each value"""
        return [[val, page] for val, page in self.filter(*filters)
                if val > -1]


class TsResults(Results):
    """
    results for Ts tests
    """

    format = 'tsformat'

    def __init__(self, string, counter_results=None):
        self.counter_results = counter_results

        string = string.strip()
        lines = string.splitlines()

        # gather the data
        self.results = []
        index = 0

        # Handle the case where we support a pagename in the results (new format)
        for line in lines:
            result = {}
            r = line.strip().split(',')
            r = [i for i in r if i]
            if len(r) <= 1:
                continue
            result['index'] = index
            result['page'] = r[0]
            #note: if we have len(r) >1, then we have pagename,raw_results
            result['runs'] = [float(i) for i in r[1:]]
            self.results.append(result)
            index += 1

        # The original case where we just have numbers and no pagename
        if not self.results:
            result = {}
            result['index'] = index
            result['page'] = 'NULL'
            result['runs'] = [float(val) for val in string.split('|')]
            self.results.append(result)


class PageloaderResults(Results):
    """
    results from a browser_dump snippet
    https://wiki.mozilla.org/Buildbot/Talos/DataFormat#browser_output.txt
    """

    format = 'tpformat'

    def __init__(self, string, counter_results=None):
        """
        - string : string of relevent part of browser dump
        - counter_results : counter results dictionary
        """

        self.counter_results = counter_results

        string = string.strip()
        lines = string.splitlines()

        # currently we ignore the metadata on top of the output (e.g.):
        # _x_x_mozilla_page_load
        # _x_x_mozilla_page_load_details
        # |i|pagename|runs|
        lines = [line for line in lines if ';' in line]

        # gather the data
        self.results = []
        for line in lines:
            result = {}
            r = line.strip('|').split(';')
            r = [i for i in r if i]
            if len(r) <= 2:
                continue
            result['index'] = int(r[0])
            result['page'] = r[1]
            result['runs'] = [float(i) for i in r[2:]]

            # fix up page
            result['page'] = self.format_pagename(result['page'])

            self.results.append(result)

    def format_pagename(self, page):
        """
        fix up the page for reporting
        """
        page = page.rstrip('/')
        if '/' in page:
            page = page.split('/')[0]
        return page


class BrowserLogResults(object):
    """parse the results from the browser log output"""

    # tokens for the report types
    report_tokens = [('tsformat', ('__start_report', '__end_report')),
                     ('tpformat', ('__start_tp_report', '__end_tp_report'))
                     ]

    # tokens for timestamps, in order (attribute, (start_delimeter, end_delimter))
    time_tokens = [('startTime', ('__startTimestamp', '__endTimestamp')),
                   ('beforeLaunchTime', ('__startBeforeLaunchTimestamp', '__endBeforeLaunchTimestamp')),
                   ('endTime', ('__startAfterTerminationTimestamp', '__endAfterTerminationTimestamp'))
                   ]

    # regular expression for failure case if we can't parse the tokens
    RESULTS_REGEX_FAIL = re.compile('__FAIL(.*?)__FAIL', re.DOTALL|re.MULTILINE)

    # regular expression for RSS results
    RSS_REGEX = re.compile('RSS:\s+([a-zA-Z0-9]+):\s+([0-9]+)$')

    # regular expression for responsiveness results
    RESULTS_RESPONSIVENESS_REGEX = re.compile('MOZ_EVENT_TRACE\ssample\s\d*?\s(\d*\.?\d*)$', re.DOTALL|re.MULTILINE)

    # classes for results types
    classes = {'tsformat': TsResults,
               'tpformat': PageloaderResults}

    # If we are using xperf, we do not upload the regular results, only xperf counters
    using_xperf = False

    def __init__(self, filename=None, results_raw=None, counter_results=None, global_counters=None):
        """
        - shutdown : whether to record shutdown results or not
        """

        self.counter_results = counter_results
        self.global_counters = global_counters

        if not (results_raw or filename):
            raise utils.talosError("Must specify filename or results_raw")

        self.filename = filename
        if results_raw is None:
            # read the file

            if not os.path.isfile(filename):
                raise utils.talosError("File '%s' does not exist" % filename)
            f = file(filename)
            exception = None
            try:
                results_raw = f.read()
            except Exception, exception:
                pass
            try:
                f.close()
            except:
                pass
            if exception:
                raise exception

        self.results_raw = results_raw

        # parse the results
        try:
            match = self.RESULTS_REGEX_FAIL.search(self.results_raw)
            if match:
                self.error(match.group(1))
                raise utils.talosError(match.group(1))

            self.parse()
        except utils.talosError:
            # TODO: consider investigating this further or adding additional information
            raise # reraise failing exception

        # accumulate counter results
        self.counters(self.counter_results, self.global_counters)

    def error(self, message):
        """raise a talosError for bad parsing of the browser log"""
        if self.filename:
            message += ' [%s]' % self.filename
        raise utils.talosError(message)

    def parse(self):
        position = -1

        # parse the report
        for format, tokens in self.report_tokens:
            report, position = self.get_single_token(*tokens)
            if report is None:
                continue
            self.browser_results = report
            self.format = format
            previous_tokens = tokens
            break
        else:
            self.error("Could not find report in browser output: %s" % self.report_tokens)

        # parse the timestamps
        for attr, tokens in self.time_tokens:

            # parse the token contents
            value, _last_token = self.get_single_token(*tokens)

            # check for errors
            if not value:
                self.error("Could not find %s in browser output: (tokens: %s)" % (attr, tokens))
            try:
                value = int(value)
            except ValueError:
                self.error("Could not cast %s to an integer: %s" % (attr, value))
            if _last_token < position:
                self.error("%s [character position: %s] found before %s [character position: %s]" % (tokens, _last_token, previous_tokens, position))

            # process
            setattr(self, attr, value)
            position = _last_token
            previous_tokens = tokens

    def get_single_token(self, start_token, end_token):
        """browser logs should only have a single instance of token pairs"""
        try:
            parts, last_token = utils.tokenize(self.results_raw, start_token, end_token)
        except AssertionError, e:
            self.error(str(e))
        if not parts:
            return None, -1 # no match
        if len(parts) != 1:
            self.error("Multiple matches for %s,%s" % (start_token, end_token))
        return parts[0], last_token

    def results(self):
        """return results instance appropriate to the format detected"""

        if self.format not in self.classes:
            raise utils.talosError("Unable to find a results class for format: %s" % repr(self.format))

        return self.classes[self.format](self.browser_results)

    ### methods for counters

    def counters(self, counter_results=None, global_counters=None):
        """accumulate all counters"""

        if counter_results is not None:
            self.rss(counter_results)

        if global_counters is not None:
            if 'shutdown' in global_counters:
                self.shutdown(global_counters)
            if 'responsiveness' in global_counters:
                global_counters['responsiveness'].extend(self.responsiveness())
            self.xperf(global_counters)

    def xperf(self, counter_results):
        """record xperf counters in counter_results dictionary"""

        counters = ['main_startup_fileio', 
                    'main_startup_netio',
                    'main_normal_fileio',
                    'main_normal_netio',
                    'nonmain_startup_fileio', 
                    'nonmain_normal_fileio',
                    'nonmain_normal_netio']

        mainthread_counter_keys = ['readcount', 'readbytes', 'writecount',
                                   'writebytes']
        mainthread_counters = ['_'.join(['mainthread', counter_key])
                               for counter_key in mainthread_counter_keys]

        if not set(counters).union(set(mainthread_counters)).intersection(counter_results.keys()):
            # no xperf counters to accumulate
            return

        filename = 'etl_output_thread_stats.csv'
        if not os.path.exists(filename):
            print "Warning: we are looking for xperf results file %s, and didn't find it" % filename
            return

        contents = file(filename).read()
        lines = contents.splitlines()
        reader = csv.reader(lines)
        header = None
        for row in reader:
            # Read CSV
            row = [i.strip() for i in row]
            if not header:
                # We are assuming the first row is the header and all other data is counters
                header = row
                continue
            values = dict(zip(header, row))

            # Format for talos
            thread = values['thread']
            counter = values['counter'].rsplit('_io_bytes', 1)[0]
            counter_name = '%s_%s_%sio' % (thread, values['stage'], counter)
            value = float(values['value'])

            # Accrue counter
            if counter_name in counter_results:
                counter_results.setdefault(counter_name, []).append(value)
                self.using_xperf = True

        if (set(mainthread_counters).intersection(counter_results.keys())):
            filename = 'etl_output.csv'
            if not os.path.exists(filename):
                print "Warning: we are looking for xperf results file %s, and didn't find it" % filename
                return

            contents = file(filename).read()
            lines = contents.splitlines()
            reader = csv.reader(lines)
            header = None
            for row in reader:
                row = [i.strip() for i in row]
                if not header:
                    # We are assuming the first row is the header and all other data is counters
                    header = row
                    continue
                values = dict(zip(header, row))
                for i, mainthread_counter in enumerate(mainthread_counters):
                    if int(values[mainthread_counter_keys[i]]) > 0:
                        counter_results.setdefault(mainthread_counter, []).append(
                            [int(values[mainthread_counter_keys[i]]),
                            values['filename']])

    def rss(self, counter_results):
        """record rss counters in counter_results dictionary"""

        counters = ['Main', 'Content']
        if not set(['%s_RSS' % i for i in counters]).intersection(counter_results.keys()):
            # no RSS counters to accumulate
            return
        for line in self.results_raw.split('\n'):
            rssmatch = self.RSS_REGEX.search(line)
            if rssmatch:
                (type, value) = (rssmatch.group(1), rssmatch.group(2))
                # type will be 'Main' or 'Content'
                counter_name = '%s_RSS' % type
                if counter_name in counter_results:
                    counter_results[counter_name].append(value)

    def shutdown(self, counter_results):
        """record shutdown time in counter_results dictionary"""
        counter_results.setdefault('shutdown', []).append(int(self.endTime - self.startTime))

    def responsiveness(self):
        return self.RESULTS_RESPONSIVENESS_REGEX.findall(self.results_raw)


def main(args=sys.argv[1:]):

    # parse command line options
    usage = '%prog [options] browser.log [...]'
    parser = optparse.OptionParser(usage=usage)
    # TODO: unify CLI options with PerfConfigurator/talos options
    parser.add_option("-a", dest='testname',
                      default='test')
    parser.add_option("-t", "--title", dest="title",
                      default='qm-pxp01')
    parser.add_option("--date", dest="date",
                      default=time.time())
    options, args = parser.parse_args()
    if not args:
        parser.print_help()
        parser.exit()

    # make a browser_config dictionary with minimal information
    browser_config = {'branch_name': '',
                      'buildid': 'testbuildid',
                      'sourcestamp': 'NULL',
                      'browser_name': 'Firefox',
                      'browser_version': '3.14'
                      }

    # filters
    # TODO: add to CLI options
    filters = [filter.ignore_max, filter.mean]

    # gather the results
    results = TalosResults(title=options.title,
                           date=options.date,
                           browser_config=browser_config,
                           filters=filters)
    for arg in args:
        browser_log = BrowserLogResults(arg)
        test_results = TestResults({'name': arg})
        test_results.add(browser_log.results())
        results.add(test_results)

    # print the graphserver-format data
    # TODO: add the ability to specify results_urls, raw_results_urls
    # and ability to output to stdout
    import tempfile
    filename = tempfile.mktemp()
    results.output(results_urls=['file://%s' % filename])
    contents = file(filename).read()
    print contents

if __name__ == '__main__':
    main()
