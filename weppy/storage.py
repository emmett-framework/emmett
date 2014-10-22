# -*- coding: utf-8 -*-
"""
    weppy.storage
    -------------

    Provide some useful classes used in weppy.

    :copyright: (c) 2014 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""


class Storage(dict):
    #: A Storage object is like a dictionary except `obj.foo` can be used
    #  in addition to `obj['foo']`, and setting obj.foo = None deletes item foo.
    __slots__ = ()
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__
    __getitem__ = dict.get
    __getattr__ = dict.get
    __repr__ = lambda self: '<Storage %s>' % dict.__repr__(self)
    __getstate__ = lambda self: None
    __copy__ = lambda self: Storage(self)


class ConfigStorage(Storage):
    #: A ConfigStorage object is like Storage, except it autogrows creating sub-
    #  Storage attributes. Useful for configurations.
    def _get(self, name):
        if not name in self.keys():
            self[name] = Storage()
        return super(ConfigStorage, self).__getitem__(name)

    __getitem__ = lambda o, v: o._get(v)
    __getattr__ = lambda o, v: o._get(v)


class ObjectProxy(object):
    #: Proxy to another object.
    __slots__ = ('__obj', '__dict__', '__name__')

    def __init__(self, obj, name=None):
        object.__setattr__(self, '_ObjectProxy__obj', obj)
        object.__setattr__(self, '__name__', name)

    def _get_robj(self):
        try:
            return getattr(self.__obj, self.__name__)
        except AttributeError:
            raise RuntimeError('no object bound to %s' % self.__name__)

    @property
    def __dict__(self):
        try:
            return self._get_robj().__dict__
        except RuntimeError:
            raise AttributeError('__dict__')

    def __repr__(self):
        try:
            obj = self._get_robj()
        except RuntimeError:
            return '<%s unbound>' % self.__class__.__name__
        return repr(obj)

    def __bool__(self):
        try:
            return bool(self._get_current_object())
        except RuntimeError:
            return False

    def __unicode__(self):
        try:
            return unicode(self._get_robj())
        except RuntimeError:
            return repr(self)

    def __dir__(self):
        try:
            return dir(self._get_current_object())
        except RuntimeError:
            return []

    def __getattr__(self, name):
        return getattr(self._get_robj(), name)

    def __setitem__(self, key, value):
        self._get_robj()[key] = value

    def __delitem__(self, key):
        del self._get_robj()[key]

    __setattr__ = lambda x, n, v: setattr(x._get_robj(), n, v)
    __delattr__ = lambda x, n: delattr(x._get_robj(), n)
    __str__ = lambda x: str(x._get_robj())
    __getitem__ = lambda x, i: x._get_robj()[i]
    __eq__ = lambda x, o: x._get_robj() == o
    __ne__ = lambda x, o: x._get_robj() != o
    __call__ = lambda x, *a, **kw: x._get_robj()(*a, **kw)
    __iter__ = lambda x: iter(x._get_robj())
    __contains__ = lambda x, i: i in x._get_robj()
