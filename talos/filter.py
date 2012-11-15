import math

"""
data filters:
takes a series of run data and applies statistical transforms to it
"""

### filters that return a scalar

def mean(series):
    """
    mean of data; needs at least one data point
    """
    return sum(series)/float(len(series))

def median(series):
    """
    median of data; needs at least one data point
    """
    series = sorted(series)
    if len(series) % 2:
        # odd
        return series[len(series)/2]
    else:
        # even
        middle = len(series)/2 # the higher of the middle 2, actually
        return 0.5*(series[middle-1] + series[middle])

def variance(series):
    """
    variance: http://en.wikipedia.org/wiki/Variance
    """

    _mean = mean(series)
    variance = sum([(i-_mean)**2 for i in series])/float(len(series))
    return variance

def stddev(series):
    """
    standard deviation: http://en.wikipedia.org/wiki/Standard_deviation
    """
    return variance(series)**0.5

def dromaeo(series):
    """
    dromaeo: https://wiki.mozilla.org/Dromaeo, pull the internal calculation out
      * This is for 'runs/s' based tests, not 'ms' tests.
      * chunksize: defined in dromaeo: page_load_test/dromaeo/webrunner.js#l8
    """
    means = []
    chunksize = 5
    series = list(dromaeo_chunks(series, chunksize))
    for i in series:
        means.append(mean(i))
    return geometric_mean(means)

def dromaeo_chunks(series, size):
    for i in xrange(0, len(series), size):
        yield series[i:i+size]

def geometric_mean(series):
    """
    geometric_mean: http://en.wikipedia.org/wiki/Geometric_mean
    """
    total = 0
    for i in series:
        total += math.log(i)
    return math.exp(total / len(series))

scalar_filters = [mean, median, max, min, variance, stddev, dromaeo]

### filters that return a list

def ignore_first(series, number=1):
    """
    ignore first datapoint
    """
    if len(series) <= number:
        # don't modify short series
        return series
    return series[number:]

def ignore(series, function):
    """
    ignore the first value of a list given by function
    """
    if len(series) <= 1:
        # don't modify short series
        return series
    series = series[:] # do not mutate the original series
    value = function(series)
    series.remove(value)
    return series

def ignore_max(series):
    """
    ignore maximum data point
    """
    return ignore(series, max)

def ignore_min(series):
    """
    ignore minimum data point
    """
    return ignore(series, min)

series_filters = [ignore_first, ignore_max, ignore_min]

### mappings

scalar_filters = dict([(i.__name__, i) for i in scalar_filters])
series_filters = dict([(i.__name__, i) for i in series_filters])

### utility functions

def parse(filter_name):
    """
    parses a filter_name like
    "ignore_first:10" to return
    ['ignore_first', [10]]
    or "foo:10.1,2,5.0" to return
    ['foo', [10.1, 2, 5.0]] .
    The filter name strings are returned versus the functions'
    as the data may need to be reserialized (e.g. PerfConfigurator.py).
    """

    sep = ':'
    argsep = ','

    def convert_to_number(string):
        """convert a string to an int or float"""
        try:
            return int(string)
        except ValueError:
            return float(string)

    args = []
    if sep in filter_name:
        filter_name, args = filter_name.split(sep, 1)
        args = [convert_to_number(arg)
                for arg in args.split(',')]
    # check validity of filter
    assert (filter_name in scalar_filters) or (filter_name in series_filters),\
           "--filter value not found in filters."
    return [filter_name, args]

def filters(*filter_names):
    """
    return a list of filter functions given a list of names
    """

    # convert to a list
    filter_names = list(filter_names)
    if not filter_names:
        return []

    # sanity checks
    allowable_filters = set(scalar_filters.keys() + series_filters.keys())
    missing = [i for i in filter_names if i not in allowable_filters]
    if missing:
        raise AssertionError("Filters not found: %s; (allowable filters: %s)" % (', '.join(missing), ', '.join(allowable_filters)))
    reducer = filter_names.pop()
    assert reducer in scalar_filters, "Last filter must return a scalar: %s, you gave %s" % (scalar_filters.keys(), reducer)
    assert set(filter_names).issubset(series_filters), "All but last filter must return a series: %s, you gave %s" % (series_filters.keys(), filter_names)

    # get the filter functions
    retval = [series_filters[i] for i in filter_names]
    retval.append(scalar_filters[reducer])
    return retval

def filters_args(_filters):
    """
    convenience function to take a list of
    [['filter_name', args]] and convert these to functions
    """
    retval = []
    filter_names = [f[0] for f in _filters]
    filter_functions = filters(*filter_names)
    for index, value in enumerate(_filters):
        retval.append([filter_functions[index], value[-1]])
    return retval

def apply(data, filters):
    """apply filters to a data series. does no safety check"""
    for f in filters:
        args = ()
        if isinstance(f, list) or isinstance(f, tuple):
            if len(f) == 2: # function, extra arguments
                f, args = f
            elif len(f) == 1: # function
                f = f[0]
            else:
                raise AssertionError("Each value must be either [filter, [args]] or [filter]")
        data = f(data, *args)
    return data
