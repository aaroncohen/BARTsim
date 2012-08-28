from itertools import islice
from math import radians, cos, sin, asin, sqrt

def window(seq, n=2):
    """
    Returns a sliding window (of width n) over data from the iterable
       s -> (s0,s1,...s[n-1]), (s1,s2,...,sn), ...
    """
    it = iter(seq)
    result = tuple(islice(it, n))
    if len(result) == n:
        yield result
    for elem in it:
        result = result[1:] + (elem,)
        yield result

def haversine(lon1, lat1, lon2, lat2):
    """
    Calculate the great circle distance between two points
    on the earth (specified in decimal degrees) in miles
    """
    # convert decimal degrees to radians
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    # haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    mi = 3959 * c
    return mi

def inv_dict(somedict):
    return dict((v,k) for k, v in somedict.iteritems())

def time_range_progress(start_time, end_time, current_time):
    length = end_time - start_time
    delta_progress = end_time - current_time
    return timedelta_to_microtime(delta_progress) / float(timedelta_to_microtime(length))

def timedelta_to_microtime(td):
    return td.microseconds + (td.seconds + td.days * 86400) * 1000000
