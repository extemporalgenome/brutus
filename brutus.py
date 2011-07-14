#!/usr/bin/python
import sys
import operator
from array import array
from functools import partial
from itertools import count, chain, product, dropwhile, takewhile
if sys.version_info < (3,):
	from itertools import imap as map
	range = xrange
	bytes = str # already the case for python >= 2.6
	arraytobytes = array.tostring
else:
	arraytobytes = array.tobytes
starchain = getattr(chain, 'from_iterable', lambda arg: chain(*arg))

__all__ = ['bruteforce']

def bruteforce(start=0, end=None, pool=range(256)):
	"""Generate brute-forced string values

	start and end input values:
		None: interpreted as 'unbounded'
		negative integers: (*don't work*) treated as offsets
		other integers: treated as string length bounds
		string: treated as start/stop sentinels.

	pool: an accepted-as-array-initializer value. Used as the char pool.

	"""

	def prepare(value, bump=0):
		try:
			number = value and int(value) or value
			string = None
		except (TypeError, ValueError):
			number = len(value) + bump
			string = arraytobytes(typedarray(value))
		if number and number < 0:
			string = number
			number = None
		return number, string

	typedarray = partial(array, 'B')
	pool = arraytobytes(typedarray(pool))
	start, first = prepare(start)
	start = start or 0
	end, last = prepare(end, 1)
	print start, first
	print end, last
	print '-----'
	if end is None:
		length = count(max(start, 1))
	else:
		length = range(max(start, 1), end)
	values = map(bytes().join, # empty byte-string
		starchain(map((lambda i: product(pool, repeat=i)), length)))
	if not start:
		values = chain(('',), values)
	# get the 'value' value of an enumerate yield
	getseqval = operator.methodcaller('__getitem__', 1)
	if isinstance(first, int): # assumed negative
		values = enumerate(values)
		if isinstance(first, int):
			values = dropwhile(partial(operator.gt, (-first,)), values)
		if isinstance(last, int):
			values = takewhile(partial(operator.lt, (-last,)), values)
		values = map(getseqval, values)
	elif first:
		values = dropwhile(partial(operator.ne, first), values)
	if isinstance(last, int):
		if not isinstance(first, int):
			values = map(getseqval,
				takewhile(partial(operator.lt, (-last,)),
					enumerate(values)))
		# else: already handled by the if isinstance(first, int) block above
	elif last:
		values = takewhile(partial(operator.gt, last), values)
	return values

if __name__ == '__main__':
	import sys
	for string in bruteforce(*map(int, sys.argv[1:3])):
		print(repr(string))
