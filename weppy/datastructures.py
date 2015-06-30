# -*- coding: utf-8 -*-
"""
    weppy.datastructures
    --------------------

    Provide some useful data structures used in weppy.

    :copyright: (c) 2015 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

import hashlib
from ._compat import pickle


class sdict(dict):
    #: like a dictionary except `obj.foo` can be used in addition to
    #  `obj['foo']`, and setting obj.foo = None deletes item foo.
    __slots__ = ()
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__
    __getitem__ = dict.get
    __getattr__ = dict.get
    __repr__ = lambda self: '<sdict %s>' % dict.__repr__(self)
    __getstate__ = lambda self: None
    __copy__ = lambda self: sdict(self)


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
        ## note: self.__dump is updated only on _modified call
        return self.__dump

    def _expires_after(self, value):
        object.__setattr__(self, '_SessionData__expires', value)
