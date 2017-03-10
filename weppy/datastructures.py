# -*- coding: utf-8 -*-
"""
    weppy.datastructures
    --------------------

    Provide some useful data structures used in weppy.

    :copyright: (c) 2014-2017 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

import copy
import hashlib
from collections import Mapping
from ._compat import pickle, string_types, iteritems
from ._internal import ImmutableList, native_itermethods


class sdict(dict):
    #: like a dictionary except `obj.foo` can be used in addition to
    #  `obj['foo']`, and setting obj.foo = None deletes item foo.
    __slots__ = ()
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__
    __getitem__ = dict.get

    # see http://stackoverflow.com/questions/10364332/how-to-pickle-python-object-derived-from-dict
    def __getattr__(self, attr):
        if attr.startswith('__'):
            raise AttributeError
        return self.get(attr, None)

    __repr__ = lambda self: '<sdict %s>' % dict.__repr__(self)
    __getstate__ = lambda self: None
    __copy__ = lambda self: sdict(self)
    __deepcopy__ = lambda self, memo: sdict(copy.deepcopy(dict(self)))


class ConfigData(sdict):
    #: like sdict, except it autogrows creating sub-sdict attributes.
    #  Useful for configurations.
    def _get(self, name):
        if name not in self.keys():
            self[name] = sdict()
        return super(ConfigData, self).__getitem__(name)

    __getitem__ = lambda o, v: o._get(v)
    __getattr__ = lambda o, v: o._get(v)


class SessionData(sdict):
    __slots__ = ('__sid', '__hash', '__expires', '__dump')

    def __init__(self, initial=None, sid=None, expires=None):
        sdict.__init__(self, initial or ())
        object.__setattr__(self, '_SessionData__dump',
                           pickle.dumps(sdict(self)))
        h = hashlib.md5(self._dump).hexdigest()
        object.__setattr__(self, '_SessionData__sid', sid)
        object.__setattr__(self, '_SessionData__hash', h)
        object.__setattr__(self, '_SessionData__expires', expires)

    @property
    def _sid(self):
        return self.__sid

    @property
    def _modified(self):
        dump = pickle.dumps(sdict(self))
        h = hashlib.md5(dump).hexdigest()
        if h != self.__hash:
            object.__setattr__(self, '_SessionData__dump', dump)
            return True
        return False

    @property
    def _expiration(self):
        return self.__expires

    @property
    def _dump(self):
        # note: self.__dump is updated only on _modified call
        return self.__dump

    def _expires_after(self, value):
        object.__setattr__(self, '_SessionData__expires', value)


def _unique_list(seq, hashfunc=None):
    seen = set()
    seen_add = seen.add
    if not hashfunc:
        return [x for x in seq
                if x not in seen and
                not seen_add(x)]
    else:
        return [x for x in seq
                if hashfunc(x) not in seen and
                not seen_add(hashfunc(x))]


class OrderedSet(set):
    def __init__(self, d=None):
        set.__init__(self)
        self._list = []
        if d is not None:
            self._list = _unique_list(d)
            set.update(self, self._list)
        else:
            self._list = []

    def add(self, element):
        if element not in self:
            self._list.append(element)
        set.add(self, element)

    def remove(self, element):
        set.remove(self, element)
        self._list.remove(element)

    def insert(self, pos, element):
        if element not in self:
            self._list.insert(pos, element)
        set.add(self, element)

    def discard(self, element):
        if element in self:
            self._list.remove(element)
            set.remove(self, element)

    def clear(self):
        set.clear(self)
        self._list = []

    def __getitem__(self, key):
        return self._list[key]

    def __iter__(self):
        return iter(self._list)

    def __add__(self, other):
        return self.union(other)

    def __repr__(self):
        return '%s(%r)' % (self.__class__.__name__, self._list)

    __str__ = __repr__

    def update(self, iterable):
        for e in iterable:
            if e not in self:
                self._list.append(e)
                set.add(self, e)
        return self

    __ior__ = update

    def union(self, other):
        result = self.__class__(self)
        result.update(other)
        return result

    __or__ = union

    def intersection(self, other):
        other = set(other)
        return self.__class__(a for a in self if a in other)

    __and__ = intersection

    def symmetric_difference(self, other):
        other = set(other)
        result = self.__class__(a for a in self if a not in other)
        result.update(a for a in other if a not in self)
        return result

    __xor__ = symmetric_difference

    def difference(self, other):
        other = set(other)
        return self.__class__(a for a in self if a not in other)

    __sub__ = difference

    def intersection_update(self, other):
        other = set(other)
        set.intersection_update(self, other)
        self._list = [a for a in self._list if a in other]
        return self

    __iand__ = intersection_update

    def symmetric_difference_update(self, other):
        set.symmetric_difference_update(self, other)
        self._list = [a for a in self._list if a in self]
        self._list += [a for a in other._list if a in self]
        return self

    __ixor__ = symmetric_difference_update

    def difference_update(self, other):
        set.difference_update(self, other)
        self._list = [a for a in self._list if a in self]
        return self

    __isub__ = difference_update


@native_itermethods(['keys', 'values', 'items'])
class EnvironHeaders(Mapping):
    def __init__(self, environ):
        self.environ = environ

    __hash__ = None

    def _key_to_headername(self, key):
        return 'HTTP_' + key.upper().replace('-', '_')

    def __getitem__(self, key):
        return self.environ[self._key_to_headername(key)]

    def __contains__(self, key):
        return self._key_to_headername(key) in self.environ

    def __iter__(self):
        for key, value in iteritems(self.environ):
            if (
                key.startswith('HTTP_') and key not in
                ('HTTP_CONTENT_TYPE', 'HTTP_CONTENT_LENGTH')
            ):
                yield (key[5:].replace('_', '-').title(), value)

    def __len__(self):
        return len(list(iter(self)))

    def get(self, key, default=None, cast=None):
        rv = self.environ.get(self._key_to_headername(key), default)
        if cast is None:
            return rv
        try:
            return cast(rv)
        except ValueError:
            return default

    def items(self):
        for key, value in self:
            yield key, value

    def keys(self):
        for key, _ in iteritems(self):
            yield key

    def values(self):
        for _, value in iteritems(self):
            yield value


@native_itermethods(['values'])
class Accept(ImmutableList):
    def __init__(self, values=()):
        if values is None:
            list.__init__(self)
            self.provided = False
        elif isinstance(values, Accept):
            self.provided = values.provided
            list.__init__(self, values)
        else:
            self.provided = True
            values = sorted(values, key=lambda x: (x[1], x[0]), reverse=True)
            list.__init__(self, values)

    def _value_matches(self, value, item):
        return item == '*' or item.lower() == value.lower()

    def __getitem__(self, key):
        if isinstance(key, string_types):
            return self.quality(key)
        return list.__getitem__(self, key)

    def quality(self, key):
        for item, quality in self:
            if self._value_matches(key, item):
                return quality
        return 0

    def __contains__(self, value):
        for item, quality in self:
            if self._value_matches(value, item):
                return True
        return False

    def __repr__(self):
        return '%s([%s])' % (
            self.__class__.__name__,
            ', '.join('(%r, %s)' % (x, y) for x, y in self)
        )

    def index(self, key):
        if isinstance(key, string_types):
            for idx, (item, quality) in enumerate(self):
                if self._value_matches(key, item):
                    return idx
            raise ValueError(key)
        return list.index(self, key)

    def find(self, key):
        try:
            return self.index(key)
        except ValueError:
            return -1

    def values(self):
        for item in self:
            yield item[0]

    def to_header(self):
        result = []
        for value, quality in self:
            if quality != 1:
                value = '%s;q=%s' % (value, quality)
            result.append(value)
        return ','.join(result)

    def __str__(self):
        return self.to_header()

    def best_match(self, matches, default=None):
        best_quality = -1
        result = default
        for server_item in matches:
            for client_item, quality in self:
                if quality <= best_quality:
                    break
                if (
                    self._value_matches(server_item, client_item) and
                    quality > 0
                ):
                    best_quality = quality
                    result = server_item
        return result

    @property
    def best(self):
        if self:
            return self[0][0]
