# -*- coding: utf-8 -*-
"""
    emmett.extensions
    -----------------

    Provides base classes to create extensions.

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

from collections import OrderedDict
from functools import wraps


class listen_signal(object):
    _inst_count_ = 0

    def __init__(self, signal):
        if signal not in MetaExtension._signals_:
            raise SyntaxError('{} is not a valid signal'.format(signal))
        self.signal = signal
        self._inst_count_ = listen_signal._inst_count_
        listen_signal._inst_count_ += 1

    def __call__(self, f):
        self.f = f
        return self


class MetaExtension(type):
    _signals_ = [
        'before_routes',
        'before_route', 'after_route',
        'before_database', 'after_database',
        'after_loop'
    ]

    def __new__(cls, name, bases, attrs):
        new_class = type.__new__(cls, name, bases, attrs)
        declared_listeners = OrderedDict()
        all_listeners = OrderedDict()
        listeners = []
        for key, value in list(attrs.items()):
            if isinstance(value, listen_signal):
                listeners.append((key, value))
        listeners.sort(key=lambda x: x[1]._inst_count_)
        declared_listeners.update(listeners)
        new_class._declared_listeners_ = declared_listeners
        for base in reversed(new_class.__mro__[1:]):
            if hasattr(base, '_declared_listeners_'):
                all_listeners.update(base._declared_listeners_)
        all_listeners.update(declared_listeners)
        new_class._all_listeners_ = all_listeners
        return new_class


class Extension(metaclass=MetaExtension):
    namespace = None
    default_config = {}

    def __init__(self, app, env, config):
        self.app = app
        self.env = env
        self.config = config
        self.__init_config()
        self.__init_listeners()

    def __init_config(self):
        for key, dval in self.default_config.items():
            self.config[key] = self.config.get(key, dval)

    def __init_listeners(self):
        self._listeners_ = []
        for name, obj in self._all_listeners_.items():
            self._listeners_.append((obj.signal, _wrap_listener(self, obj.f)))

    def on_load(self):
        pass


def _wrap_listener(ext, f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        return f(ext, *args, **kwargs)
    return wrapped
