# -*- coding: utf-8 -*-
"""
    weppy._compat
    -------------

    Some py2/py3 compatibility support.

    :copyright: (c) 2014-2017 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

import sys
import hashlib

PY2 = sys.version_info[0] == 2
_identity = lambda x: x

if PY2:
    from Cookie import SimpleCookie
    from cStringIO import StringIO
    import cPickle as pickle
    import copy_reg as copyreg
    iterkeys = lambda d: d.iterkeys()
    itervalues = lambda d: d.itervalues()
    iteritems = lambda d: d.iteritems()

    text_type = unicode
    integer_types = (int, long)
    string_types = (str, unicode)
    basestring = basestring

    reduce = reduce
    xrange = xrange
    hashlib_md5 = hashlib.md5
    hashlib_sha1 = hashlib.sha1

    def implements_iterator(cls):
        cls.next = cls.__next__
        del cls.__next__
        return cls

    def implements_bool(cls):
        cls.__nonzero__ = cls.__bool__
        del cls.__bool__
        return cls

    def implements_to_string(cls):
        cls.__unicode__ = cls.__str__
        cls.__str__ = lambda x: x.__unicode__().encode('utf-8')
        return cls

    exec('def reraise(tp, value, tb=None):\n raise tp, value, tb')

    def to_bytes(obj, charset='utf8', errors='strict'):
        if obj is None:
            return None
        if isinstance(obj, (bytes, bytearray, buffer)):
            return bytes(obj)
        if isinstance(obj, unicode):
            return obj.encode(charset, errors)
        raise TypeError('Expected bytes')

    def to_native(obj, charset='utf8', errors='strict'):
        if obj is None or isinstance(obj, str):
            return obj
        return obj.encode(charset, errors)

else:
    from http.cookies import SimpleCookie
    from io import StringIO
    import pickle
    import copyreg
    iterkeys = lambda d: iter(d.keys())
    itervalues = lambda d: iter(d.values())
    iteritems = lambda d: iter(d.items())

    text_type = str
    integer_types = (int, )
    string_types = (str,)
    basestring = str

    from functools import reduce
    xrange = range
    hashlib_md5 = lambda s: hashlib.md5(bytes(s, 'utf8'))
    hashlib_sha1 = lambda s: hashlib.sha1(bytes(s, 'utf8'))

    implements_iterator = _identity
    implements_bool = _identity
    implements_to_string = _identity

    def reraise(tp, value, tb=None):
        if value.__traceback__ is not tb:
            raise value.with_traceback(tb)
        raise value

    def to_bytes(obj, charset='utf8', errors='strict'):
        if obj is None:
            return None
        if isinstance(obj, (bytes, bytearray, memoryview)):
            return bytes(obj)
        if isinstance(obj, str):
            return obj.encode(charset, errors)
        raise TypeError('Expected bytes')

    def to_native(obj, charset='utf8', errors='strict'):
        if obj is None or isinstance(obj, str):
            return obj
        return obj.decode(charset, errors)


def with_metaclass(meta, *bases):
    """Create a base class with a metaclass."""
    # This requires a bit of explanation: the basic idea is to make a
    # dummy metaclass for one level of class instantiation that replaces
    # itself with the actual metaclass.
    class metaclass(type):
        def __new__(cls, name, this_bases, d):
            return meta(name, bases, d)
    return type.__new__(metaclass, 'temporary_class', (), {})


def to_unicode(obj, charset='utf8', errors='strict'):
    if obj is None:
        return None
    if not isinstance(obj, bytes):
        return text_type(obj)
    return obj.decode(charset, errors)
