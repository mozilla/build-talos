"""
objects for parsing Talos results
"""

import filter
import re
import utils

__all__ = ['BrowserLogResults', 'PageloaderResults']

class BrowserLogResults(object):
    """
    parse the results from the browser log
    """

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

    # regular expression for responsiveness results
    RESULTS_RESPONSIVENESS_REGEX = re.compile('MOZ_EVENT_TRACE\ssample\s\d*?\s(\d*?)$', re.DOTALL|re.MULTILINE)

    def __init__(self, results_raw, filename=None):

        self.filename = filename
        self.results_raw = results_raw
        try:
            self.parse()
        except utils.talosError:
            # see we can find a reason for the failure
            match = self.RESULTS_REGEX_FAIL.search(self.results_raw)
            if match:
                self.error(match.group(1))
                raise utils.talosError(match.group(1))
            raise # reraise failing exception

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

    def responsiveness(self):
        return self.RESULTS_RESPONSIVENESS_REGEX.findall(self.results_raw)


class PageloaderResults(object):
    """
    results from a browser_dump snippet
    https://wiki.mozilla.org/Buildbot/Talos/DataFormat#browser_output.txt
    """

    def __init__(self, string):
        """
        - string : string of browser dump
        """
        string = string.strip()
        lines = string.splitlines()

        # currently we ignore the metadata on top of the output
        lines = [line for line in lines if ';' in line]

        # gather the data
        self.results = []
        for line in lines:
            result = {}
            r = line.strip('|').split(';')
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

    def raw_values(self):
        return dict([(result['page'], result['runs']) for result in self.results])

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
