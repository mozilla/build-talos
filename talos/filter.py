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

### filters that return a list

def ignore_first(series):
    """
    ignore first datapoint
    """
    return series[1:]

