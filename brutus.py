#!/usr/bin/python
import sys
import operator
from copy import copy
from array import array
from itertools import count, chain, product, dropwhile, takewhile, islice

##### EVERYTHING STARTING HERE IS 2.X VS 3.X DUAL-COMPAT #####
try:
    from functools import partial
except ImportError:
    def partial(func, *args, **keywords):
        warnings.warn("Prior to python2.5, performance will be slow due to "
            "lack of functools.partial")
        def newfunc(*fargs, **fkeywords):
            newkeywords = keywords.copy()
            newkeywords.update(fkeywords)
            return func(*(args + fargs), **newkeywords)
        newfunc.func = func
        newfunc.args = args
        newfunc.keywords = keywords
        return newfunc

callable = getattr(__builtins__, 'callable',
    lambda x: isinstance(x, collections.Callable))
        
if sys.version_info < (3,):
    # This block makes python2.x look a lot more like python3.x
    from itertools import imap as map
    import warnings
    range = xrange
    bytes = str # already the case for python >= 2.6
    arraytobytes = array.tostring
    intstobytes = bytes().join
    if hasattr(chain, 'from_iterable'):
        starchain_native = starchain_python = chain.from_iterable
    else:
        def starchain_native(iterables):
            warnings.warn("Prior to python2.6, initial delay may be long "
                "when calling generate with a finite 'stop' value")
            return chain(*iterables)

        def starchain_python(iterables):
            warnings.warn("Prior to python2.6, performance will be abysmal "
                "when calling generate with an 'stop' value of None")
            for it in iterables:
                for element in it:
                    yield element
else:
    intstobytes = bytes
    arraytobytes = array.tobytes # array.tostring deprecated in 3.2
    starchain_python = starchain_native = chain.from_iterable
##### END DUAL-COMPAT CODE #####

__all__ = ['generate']

class generate(object):
    undefined = object()

    def __init__(self, start=1, stop=None, pool=range(256)):
        """Generate brute-force byte values

        start: least int number of characters to generate.
        stop:  int upper bound (non-inclusive) on number of characters to
               generate (or None for no limit)
        pool:  an accepted-as-array-initializer value used as the char pool.
               Iterables of strings (including strings), and iterables of
               ints in the range 0-255 will work.
        
        """

        print(start, stop)
        if start < 0 or stop < 0:
            raise ValueError("start and stop must be non-negative integers")

        pool = arraytobytes(array('B', set(pool)))
        start = start or 0
        if stop is None:
            length = count(max(start, 1))
            starchain = starchain_python
        else:
            length = range(max(start, 1), stop)
            starchain = starchain_native
        stream = map(intstobytes, # produces byte-strings
            starchain( # flattens yielded values
                map( # produces iterables grouped by string length
                    (lambda i: product(pool, repeat=i)), length)))
        if not start:
            stream = chain([bytes()], stream)
        self._stream = stream
        self._scan_streams = (stream, stream)
        self._filter_streams = []
        self._stream_offset = stream
        self._scan_objects = (None, None)
        self._scan_inclusivities = (True, True)
        self._filters = []
        self._filters_inversed = []
    
    __iter__ = lambda self: self._stream_offset
    scan_start = property(lambda self: self._scan_start)
    scan_stop = property(lambda self: self._scan_stop)
    filter_functions = property(lambda self: self._filter_functions[:])
    filter_inversed = property(lambda self: self._filter_inversed)

    def scan(self, start=undefined, stop=undefined, inclusive=True):
        """Return instance with byte-string bounds applied

        TODO
        
        Implementation detail: this silently discards values before
        the given start string is matched. Future efforts may turn this
        into an intelligent seek.

        """

        if start is stop is undefined:
            raise TypeError("Either or both of start or stop "
                "must be provided.")
        inclusive = bool(inclusive)
        if self._is_same_scan(start, stop, inclusive):
            return self
        self = copy(self)
        if start is undefined:
            start = self._scan_objects[0]
            start_inclusive = self._scan_inclusivities[0]
            start_stream = self._scan_streams[0]
        else:
            if inclusive:
                attr, default = '__gt__', operator.gt
            else:
                attr, default = '__ge__', operator.ge
            start_inclusive = inclusive
            start_stream = self._scan_wrap(self._stream, dropwhile,
                start, attr, default)
        if stop is undefined:
            # start must have been specified
            stop = self._scan_objects[1]
            stop_inclusive = self._scan_inclusivities[1]
        else:
            stop_inclusive = inclusive
        if stop_inclusive:
            attr, default = '__le__', operator.le
        else:
            attr, default = '__lt__', operator.lt
        stop_stream = self._scan_wrap(start_stream, takewhile,
            stop, attr, default)
        self._scan_objects = (start, stop)
        self._scan_streams = (start_stream, stop_stream)
        self._scan_inclusivities = (start_inclusive, stop_inclusive)
        self._refilter()
        return self

    def _is_same_scan(self, start, stop, inclusive):
        return (self._is_same_scan_part(0, start, inclusive) and
            self._is_same_scan_part(1, stop, inclusive))

    def _is_same_scan_part(self, index, object, inclusive):
        if object is self._scan_objects[index]:
            if inclusive != self._scan_inclusivities[index]:
                return False
        elif object is not self.undefined:
            return False
        return True

    def _scan_wrap(self, stream, wrapper, object, attr, default):    
        if object:
            func = getattr(object, attr, None) or partial(default, object)
            return wrapper(func, stream)
        else:
            return stream
    
    def filter(self, function=None, inverse=False):
        """Return instance with filter applied"""

        inverse = bool(inverse)
        if self._has_same_filter(function, inverse):
            return self
        self = copy(self)
        self._filter(function, inverse)
        return self

    def _has_same_filter(self, function, inverse):
        for func, inv in zip(self._filters, self._filters_inversed):
            if function is func and inverse == inv:
                return True
        return False

    def _filter(self, function=None, inverse=False):
        if not function:
            self._filtered_streams = []
            self._filters = []
            self._filters_inversed = []
        else:
            if not callable(function):
                raise TypeError("A callable or None must be passed to filter")
            stream = self._last_filter_stream()
            stream = self._apply_filter(stream, function, inverse)
            self._filtered_streams.append(stream)
            self._filters.append(function)
            self._filters_inversed.append(inverse)
        self._offset()
    
    def _refilter(self):
        stream = self._scan_streams[1]
        streams = []
        for function, inverse in zip(self._filters, self._filters_inversed):
            stream = self._apply_filter(stream, function, inverse)
            streams.append(stream)
        self._filter_streams = streams
        self._offset()

    def _apply_filter(self, stream, function, inverse):
        if inverse:
            return filter_false(function, stream)
        else:
            return filter(function, stream)
    
    def _last_filter_stream(self):
        if self._filter_streams:
            return self._filter_streams[-1]
        else:
            return self._scan_streams[-1]

    def offset(self, start=0, stop=None, step=1, length=None):
        if length is not None:
            if stop is not None:
                raise ValueError("Either or both of stop or "
                    "length must be None")
            stop = start + length
        self = copy(self)
        self._offset(start, stop, step)
        return self
    
    #_empty_offset = lambda self: self._stream_offset is self._stream_filtered

    def _offset(self, start=0, stop=None, step=1):
        stream = self._last_filter_stream()
        if start == 0 and stop is None and step == 1:
            self._offset_stream = stream
        else:
            self._stream_offset = islice(stream, start, stop, step)


if __name__ == '__main__':
    try:
        source = generate(*(map(int, sys.argv[1:3])))
        list(dropwhile(operator.truth, map(print, map(repr, source))))
    except IOError:
        pass
