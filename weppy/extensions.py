# -*- coding: utf-8 -*-
"""
    weppy.extensions
    ----------------

    Provides base classes to create extensions.

    :copyright: (c) 2014-2017 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

from ._compat import with_metaclass, iteritems
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
        'before_routes', 'before_database', 'after_database',
        'before_route', 'after_route']

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


class Extension(with_metaclass(MetaExtension)):
    namespace = None
    default_config = {}

    def __init__(self, app, env, config):
        self.app = app
        self.env = env
        self.config = config
        self.__init_config()
        self.__init_listeners()

    def __init_config(self):
        for key, dval in iteritems(self.default_config):
            self.config[key] = self.config.get(key, dval)

    def __init_listeners(self):
        self._listeners_ = []
        for name, obj in iteritems(self._all_listeners_):
            self._listeners_.append((obj.signal, _wrap_listener(self, obj.f)))

    def on_load(self):
        pass


class TemplateExtension(object):
    namespace = None
    file_extension = None
    lexers = {}

    def __init__(self, env, config):
        self.env = env
        self.config = config

    def preload(self, path, name):
        return path, name

    def preprocess(self, source, name):
        return source

    def inject(self, context):
        pass


class TemplateLexer(object):
    evaluate_value = True

    def __init__(self, extension):
        self.ext = extension

    def __call__(self, parser, value=None):
        self.parser = parser
        if self.evaluate_value and value is not None:
            value = eval(value, self.parser.context)
        self.process(value)

    @property
    def stack(self):
        return self.parser.stack

    @property
    def top(self):
        return self.parser.stack[-1]

    def process(self, value):
        return value


def _wrap_listener(ext, f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        return f(ext, *args, **kwargs)
    return wrapped
