class PageloaderResults(object):
    """
    results from a browser_dump snippet
    https://wiki.mozilla.org/Buildbot/Talos/DataFormat#browser_output.txt
    """

    fields = ('index', 'page', 'median', 'mean', 'min', 'max')
    numeric = ('median', 'mean', 'min', 'max')

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
            r = line.split(';')
            for index, field in enumerate(self.fields):
                result[field] = r[index]
            for field in self.numeric:
                result[field] = float(result[field])
            result['runs'] = [float(i) for i in r[6:]]

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
            for _filter in filters:
                data = _filter(data)
            retval.append([data, page])
        return retval

    def value(self, field):
        return [[result[field], result['page']]
                for result in self.results]

    def median(self):
        return self.value('median')

    def mean(self):
        return self.value('mean')

    def max(self):
        return self.value('max')

    def min(self):
        return self.value('min')
