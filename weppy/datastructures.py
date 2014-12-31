# -*- coding: utf-8 -*-
"""
    weppy.datastructures
    --------------------

    Provide some useful data structures used in weppy.

    :copyright: (c) 2014 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""


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
        if not name in self.keys():
            self[name] = sdict()
        return super(ConfigData, self).__getitem__(name)

    __getitem__ = lambda o, v: o._get(v)
    __getattr__ = lambda o, v: o._get(v)
