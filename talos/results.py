import filter

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
