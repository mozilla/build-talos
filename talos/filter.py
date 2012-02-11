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

scalar_filters = [mean, median, max, min]

### filters that return a list

def ignore_first(series):
    """
    ignore first datapoint
    """
    if len(series) <= 1:
        # don't modify short series
        return series
    return series[1:]

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

def apply(data, filters):
    """apply filters to a data series. does no safety check"""
    for f in filters:
        data = f(data)
    return data
