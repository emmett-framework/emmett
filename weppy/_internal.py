# -*- coding: utf-8 -*-
"""
    weppy._internal
    ---------------

    Provides internally used helpers and objects.

    :copyright: (c) 2014-2017 by Giovanni Barillari

    Several parts of this code comes from Flask and Werkzeug.
    :copyright: (c) 2014 by Armin Ronacher.

    :license: BSD, see LICENSE for more details.
"""

import datetime
import os
import pkgutil
import sys
import warnings
from functools import partial
from ._compat import PY2, implements_iterator


def _is_immutable(self):
    raise TypeError('%r objects are immutable' % self.__class__.__name__)


#: internal datastructures
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


class ViewItems(object):
    def __init__(self, obj, method, repr_name, *a, **kw):
        self.__obj = obj
        self.__method = method
        self.__repr_name = repr_name
        self.__a = a
        self.__kw = kw

    def __get_items(self):
        return getattr(self.__obj, self.__method)(*self.__a, **self.__kw)

    def __repr__(self):
        return '%s(%r)' % (self.__repr_name, list(self.__get_items()))

    def __iter__(self):
        return iter(self.__get_items())


class ImmutableListMixin(object):
    _hash_cache = None

    def __hash__(self):
        if self._hash_cache is not None:
            return self._hash_cache
        rv = self._hash_cache = hash(tuple(self))
        return rv

    def __reduce_ex__(self, protocol):
        return type(self), (list(self),)

    def __delitem__(self, key):
        _is_immutable(self)

    def __iadd__(self, other):
        _is_immutable(self)
    __imul__ = __iadd__

    def __setitem__(self, key, value):
        _is_immutable(self)

    def append(self, item):
        _is_immutable(self)
    remove = append

    def extend(self, iterable):
        _is_immutable(self)

    def insert(self, pos, value):
        _is_immutable(self)

    def pop(self, index=-1):
        _is_immutable(self)

    def reverse(self):
        _is_immutable(self)

    def sort(self, cmp=None, key=None, reverse=None):
        _is_immutable(self)


class ImmutableList(ImmutableListMixin, list):
    def __repr__(self):
        return '%s(%s)' % (
            self.__class__.__name__, list.__repr__(self)
        )


@implements_iterator
class LimitedStream(object):
    def __init__(self, stream, limit):
        self._read = stream.read
        self._readline = stream.readline
        self._pos = 0
        self.limit = limit

    def __iter__(self):
        return self

    @property
    def is_exhausted(self):
        """If the stream is exhausted this attribute is `True`."""
        return self._pos >= self.limit

    def on_exhausted(self):
        """This is called when the stream tries to read past the limit.
        The return value of this function is returned from the reading
        function.
        """
        # Read null bytes from the stream so that we get the
        # correct end of stream marker.
        return self._read(0)

    def on_disconnect(self):
        raise Exception

    def exhaust(self, chunk_size=1024 * 64):
        """Exhaust the stream.  This consumes all the data left until the
        limit is reached.

        :param chunk_size: the size for a chunk.  It will read the chunk
                           until the stream is exhausted and throw away
                           the results.
        """
        to_read = self.limit - self._pos
        chunk = chunk_size
        while to_read > 0:
            chunk = min(to_read, chunk)
            self.read(chunk)
            to_read -= chunk

    def read(self, size=None):
        """Read `size` bytes or if size is not provided everything is read.

        :param size: the number of bytes read.
        """
        if self._pos >= self.limit:
            return self.on_exhausted()
        if size is None or size == -1:  # -1 is for consistence with file
            size = self.limit
        to_read = min(self.limit - self._pos, size)
        try:
            read = self._read(to_read)
        except (IOError, ValueError):
            return self.on_disconnect()
        if to_read and len(read) != to_read:
            return self.on_disconnect()
        self._pos += len(read)
        return read

    def readline(self, size=None):
        """Reads one line from the stream."""
        if self._pos >= self.limit:
            return self.on_exhausted()
        if size is None:
            size = self.limit - self._pos
        else:
            size = min(size, self.limit - self._pos)
        try:
            line = self._readline(size)
        except (ValueError, IOError):
            return self.on_disconnect()
        if size and not line:
            return self.on_disconnect()
        self._pos += len(line)
        return line

    def readlines(self, size=None):
        """Reads a file into a list of strings.  It calls :meth:`readline`
        until the file is read to the end.  It does support the optional
        `size` argument if the underlaying stream supports it for
        `readline`.
        """
        last_pos = self._pos
        result = []
        if size is not None:
            end = min(self.limit, last_pos + size)
        else:
            end = self.limit
        while 1:
            if size is not None:
                size -= last_pos - self._pos
            if self._pos >= end:
                break
            result.append(self.readline(size))
            if size is not None:
                last_pos = self._pos
        return result

    def __next__(self):
        line = self.readline()
        if not line:
            raise StopIteration()
        return line


@implements_iterator
class ClosingIterator(object):
    def __init__(self, iterable, callbacks=None):
        iterator = iter(iterable)
        self._next = partial(next, iterator)
        if callbacks is None:
            callbacks = []
        elif callable(callbacks):
            callbacks = [callbacks]
        else:
            callbacks = list(callbacks)
        iterable_close = getattr(iterator, 'close', None)
        if iterable_close:
            callbacks.insert(0, iterable_close)
        self._callbacks = callbacks

    def __iter__(self):
        return self

    def __next__(self):
        return self._next()

    def close(self):
        for callback in self._callbacks:
            callback()


#: decorators
def native_itermethods(names):
    if not PY2:
        return lambda x: x

    def setviewmethod(cls, name):
        viewmethod_name = 'view%s' % name
        viewmethod = lambda self, *a, **kw: ViewItems(
            self, name, 'view_%s' % name, *a, **kw)
        viewmethod.__doc__ = \
            '"""`%s()` object providing a view on %s"""' % (
                viewmethod_name, name)
        setattr(cls, viewmethod_name, viewmethod)

    def setitermethod(cls, name):
        itermethod = getattr(cls, name)
        setattr(cls, 'iter%s' % name, itermethod)
        listmethod = lambda self, *a, **kw: list(itermethod(self, *a, **kw))
        listmethod.__doc__ = \
            'Like :py:meth:`iter%s`, but returns a list.' % name
        setattr(cls, name, listmethod)

    def wrap(cls):
        for name in names:
            setitermethod(cls, name)
            setviewmethod(cls, name)
        return cls
    return wrap


#: deprecation helpers
class RemovedInNextVersionWarning(DeprecationWarning):
    pass


class deprecated(object):
    def __init__(self, old_method_name, new_method_name, class_name=None, s=0):
        self.class_name = class_name
        self.old_method_name = old_method_name
        self.new_method_name = new_method_name
        self.additional_stack = s

    def __call__(self, f):
        def wrapped(*args, **kwargs):
            warn_of_deprecation(
                self.old_method_name, self.new_method_name, self.class_name,
                3 + self.additional_stack)
            return f(*args, **kwargs)
        return wrapped


warnings.simplefilter('always', RemovedInNextVersionWarning)


def warn_of_deprecation(old_name, new_name, prefix=None, stack=2):
    msg = "%(old)s is deprecated, use %(new)s instead."
    if prefix:
        msg = "%(prefix)s." + msg
    warnings.warn(
        msg % {'old': old_name, 'new': new_name, 'prefix': prefix},
        RemovedInNextVersionWarning, stack)


#: app init helpers
def get_root_path(import_name):
    """Returns the path of the package or cwd if that cannot be found."""
    # Module already imported and has a file attribute.  Use that first.
    mod = sys.modules.get(import_name)
    if mod is not None and hasattr(mod, '__file__'):
        return os.path.dirname(os.path.abspath(mod.__file__))

    # Next attempt: check the loader.
    loader = pkgutil.get_loader(import_name)

    # Loader does not exist or we're referring to an unloaded main module
    # or a main module without path (interactive sessions), go with the
    # current working directory.
    if loader is None or import_name == '__main__':
        return os.getcwd()

    # For .egg, zipimporter does not have get_filename until Python 2.7.
    # Some other loaders might exhibit the same behavior.
    if hasattr(loader, 'get_filename'):
        filepath = loader.get_filename(import_name)
    else:
        # Fall back to imports.
        __import__(import_name)
        mod = sys.modules[import_name]
        filepath = getattr(mod, '__file__', None)

        # If we don't have a filepath it might be because we are a
        # namespace package.  In this case we pick the root path from the
        # first module that is contained in our package.
        if filepath is None:
            raise RuntimeError('No root path can be found for the provided '
                               'module "%s".  This can happen because the '
                               'module came from an import hook that does '
                               'not provide file name information or because '
                               'it\'s a namespace package.  In this case '
                               'the root path needs to be explicitly '
                               'provided.' % import_name)

    # filepath is import_name.py for a module, or __init__.py for a package.
    return os.path.dirname(os.path.abspath(filepath))


def create_missing_app_folders(app):
    try:
        for subfolder in ['languages', 'logs', 'static']:
            path = os.path.join(app.root_path, subfolder)
            if not os.path.exists(path):
                os.mkdir(path)
    except:
        pass


#: monkey patches
class IsoformatJSONMixin(object):
    def __json__(self):
        return self.isoformat()


class Date(datetime.date, IsoformatJSONMixin):
    pass


class Time(datetime.time, IsoformatJSONMixin):
    pass


class DateTime(datetime.datetime):
    def date(self):
        d = super(DateTime, self).date()
        return Date(d.year, d.month, d.day)

    def time(self):
        t = super(DateTime, self).time()
        return Time(t.hour, t.minute, t.second, t.microsecond, t.tzinfo)

    def __json__(self):
        return self.strftime('%Y-%m-%dT%H:%M:%S.%f%_z')


def _pendulum_to_json(obj):
    return obj.strftime('%Y-%m-%dT%H:%M:%S.%f%_z')


# datetime.date = Date
# datetime.time = Time
# datetime.datetime = DateTime
# pendulum.Pendulum.__json__ = _pendulum_to_json
