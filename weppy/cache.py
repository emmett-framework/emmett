# -*- coding: utf-8 -*-
"""
    weppy.cache
    -----------

    Provides a caching system.

    :copyright: (c) 2014-2017 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

import os
import time
import heapq
import threading
import tempfile
from functools import wraps

from ._compat import (
    pickle, integer_types, iteritems, hashlib_md5, hashlib_sha1)
from .libs.portalocker import LockedFile

__all__ = ['Cache']


class CacheDecorator(object):
    def __init__(self, handler, key, duration):
        self._cache = handler
        self.key = key
        self.duration = duration

    def _hash_component(self, key, data):
        return ''.join([key, "{", repr(data), "}"])

    def _build_hash(self, args, kwargs):
        components = []
        components.append(self._hash_component('args', args))
        components.append(
            self._hash_component(
                'kwargs', [(key, kwargs[key]) for key in sorted(kwargs)]))
        return hashlib_sha1(':'.join(components)).hexdigest()

    def _build_ctx_key(self, args, kwargs):
        if not args and not kwargs:
            return self.key
        return self.key + ":" + self._build_hash(args, kwargs)

    def __call__(self, f):
        @wraps(f)
        def wrap(*args, **kwargs):
            key = self._build_ctx_key(args, kwargs)
            return self._cache.get_or_set(
                key, lambda: f(*args, **kwargs), self.duration)
        if not self.key:
            self.key = f.__module__ + '.' + f.__name__
        return wrap


class CacheHandler(object):
    def __init__(self, prefix='', default_expire=300):
        self._default_expire = default_expire
        self._prefix = prefix

    @staticmethod
    def _key_prefix_(method):
        @wraps(method)
        def wrap(self, key=None, *args, **kwargs):
            key = self._prefix + key if key is not None else key
            return method(self, key, *args, **kwargs)
        return wrap

    @staticmethod
    def _convert_duration_(method):
        @wraps(method)
        def wrap(self, key, value, duration='default'):
            if duration is None:
                duration = 60 * 60 * 24 * 365
            if duration == "default":
                duration = self._default_expire
            now = time.time()
            return method(self, key, value, now=now, expiration=now + duration)
        return wrap

    def __call__(self, key=None, function=None, duration='default'):
        if function:
            return self.get_or_set(key, function, duration)
        return CacheDecorator(self, key, duration)

    def get_or_set(self, key, function, duration='default'):
        value = self.get(key)
        if value is None:
            value = function()
            self.set(key, value, duration)
        return value

    def get(self, key):
        return None

    def set(self, key, value, duration):
        pass

    def clear(self, key=None):
        pass


class RamElement(object):
    __slots__ = ('value', 'exp', 'acc')

    def __init__(self, value, exp, acc):
        self.value = value
        self.exp = exp
        self.acc = acc


class RamCache(CacheHandler):
    lock = threading.RLock()
    data = {}
    _heap_exp = []
    _heap_acc = []

    def __init__(self, prefix='', threshold=500, default_expire=300):
        super(RamCache, self).__init__(
            prefix=prefix, default_expire=default_expire)
        self._threshold = threshold

    def _prune(self):
        now = time.time()
        # remove expired items
        while self._heap_exp:
            exp, rk = heapq.heappop(self._heap_exp)
            if exp < now:
                self._heap_acc.remove((self.data[rk].acc, rk))
                del self.data[rk]
            else:
                heapq.heappush(self._heap_exp, (exp, rk))
                break
        # remove threshold exceding elements
        while len(self.data) > self._threshold:
            rk = heapq.heappop(self._heap_acc)[1]
            self._heap_exp.remove((self.data[rk].exp, rk))
            del self.data[rk]

    @CacheHandler._key_prefix_
    def get(self, key):
        try:
            with self.lock:
                element = self.data[key]
                now = time.time()
                if element.exp < now:
                    return None
                self._heap_acc.remove((element.acc, key))
                element.acc = now
                heapq.heappush(self._heap_acc, (element.acc, key))
            val = element.value
        except KeyError:
            return None
        return val

    @CacheHandler._key_prefix_
    @CacheHandler._convert_duration_
    def set(self, key, value, **kwargs):
        with self.lock:
            self._prune()
            heapq.heappush(self._heap_exp, (kwargs['expiration'], key))
            heapq.heappush(self._heap_acc, (kwargs['now'], key))
            self.data[key] = RamElement(
                value, kwargs['expiration'], kwargs['now'])

    @CacheHandler._key_prefix_
    def clear(self, key=None):
        with self.lock:
            if key is not None:
                try:
                    rv = self.data[key]
                    self._heap_acc.remove((rv.acc, key))
                    self._heap_exp.remove((rv.exp, key))
                    del self.data[key]
                    return
                except Exception:
                    return
            self.data.clear()
            self._heap_acc = []
            self._heap_exp = []


class DiskCache(CacheHandler):
    lock = threading.RLock()
    _fs_transaction_suffix = '.__wp_cache'
    _fs_mode = 0o600

    def __init__(self, cache_dir='cache', threshold=500, default_expire=300):
        super(DiskCache, self).__init__(default_expire=default_expire)
        self._threshold = threshold
        from .expose import Expose
        self._path = os.path.join(Expose.application.root_path, cache_dir)
        #: create required paths if needed
        if not os.path.exists(self._path):
            os.mkdir(self._path)

    def _get_filename(self, key):
        khash = hashlib_md5(key).hexdigest()
        return os.path.join(self._path, khash)

    def _del_file(self, filename):
        try:
            os.remove(filename)
        except Exception:
            pass

    def _list_dir(self):
        return [os.path.join(self._path, fn) for fn in os.listdir(self._path)
                if not fn.endswith(self._fs_transaction_suffix)]

    def _prune(self):
        with self.lock:
            entries = self._list_dir()
            if len(entries) > self._threshold:
                now = time.time()
                try:
                    for i, fpath in enumerate(entries):
                        remove = False
                        f = LockedFile(fpath, 'rb')
                        #with open(fpath, 'rb') as f:
                        exp = pickle.load(f.file)
                        f.close()
                        remove = exp <= now or i % 3 == 0
                        if remove:
                            self._del_file(fpath)
                except Exception:
                    pass

    def get(self, key):
        filename = self._get_filename(key)
        try:
            with self.lock:
                now = time.time()
                f = LockedFile(filename, 'rb')
                #with open(filename, 'rb') as f:
                exp = pickle.load(f.file)
                if exp < now:
                    f.close()
                    return None
                val = pickle.load(f.file)
                f.close()
        except Exception:
            return None
        return val

    @CacheHandler._convert_duration_
    def set(self, key, value, **kwargs):
        filename = self._get_filename(key)
        with self.lock:
            self._prune()
            try:
                fd, tmp = tempfile.mkstemp(
                    suffix=self._fs_transaction_suffix, dir=self._path)
                with os.fdopen(fd, 'wb') as f:
                    pickle.dump(kwargs['expiration'], f, 1)
                    pickle.dump(value, f, pickle.HIGHEST_PROTOCOL)
                os.rename(tmp, filename)
                os.chmod(filename, self._fs_mode)
            except Exception:
                pass

    def clear(self, key=None):
        with self.lock:
            if key is not None:
                filename = self._get_filename(key)
                try:
                    os.remove(filename)
                    return
                except Exception:
                    return
            for name in self._list_dir():
                self._del_file(name)


class RedisCache(CacheHandler):
    def __init__(
        self, host='localhost', port=6379, password=None, db=0,
        default_expire=300, prefix='', **kwargs
    ):
        super(RedisCache, self).__init__(
            prefix=prefix, default_expire=default_expire)
        try:
            import redis
        except ImportError:
            raise RuntimeError('no redis module found')
        self._cache = redis.Redis(
            host=host, port=port, password=password, db=db, **kwargs)

    def _dump_obj(self, value):
        if type(value) in integer_types:
            return str(value).encode('ascii')
        return b'!' + pickle.dumps(value)

    def _load_obj(self, value):
        if value is None:
            return None
        if value.startswith(b'!'):
            try:
                return pickle.loads(value[1:])
            except pickle.PickleError:
                return None
        try:
            return int(value)
        except ValueError:
            return None

    @CacheHandler._key_prefix_
    def get(self, key):
        return self._load_obj(self._cache.get(key))

    @CacheHandler._key_prefix_
    @CacheHandler._convert_duration_
    def set(self, key, value, **kwargs):
        dumped = self._dump_obj(value)
        return self._cache.setex(
            name=key, value=dumped, time=kwargs['expiration'])

    @CacheHandler._key_prefix_
    def clear(self, key=None):
        if key is not None:
            if key.endswith('*'):
                keys = self._cache.delete(self._cache.keys(key))
                if keys:
                    self._cache.delete(*keys)
                return
            self._cache.delete(key)
            return
        if self._prefix:
            keys = self._cache.keys(self._prefix + '*')
            if keys:
                self._cache.delete(*keys)
            return
        self._cache.flushdb()


class Cache(object):
    def __init__(self, **kwargs):
        #: load handlers
        handlers = []
        for key, val in iteritems(kwargs):
            if key == "default":
                continue
            handlers.append((key, val))
        if not handlers:
            handlers.append(('ram', RamCache()))
        #: set handlers
        for name, handler in handlers:
            setattr(self, name, handler)
        _default_handler_name = kwargs.get('default', handlers[0][0])
        self._default_handler = getattr(self, _default_handler_name)

    def __call__(self, key=None, function=None, duration='default'):
        return self._default_handler(key, function, duration)

    def get(self, key):
        return self._default_handler.get(key)

    def set(self, key, value, duration='default'):
        self._default_handler.set(key, value, duration)

    def get_or_set(self, key, function, duration='default'):
        return self._default_handler.get_or_set(key, function, duration)

    def clear(self, key=None):
        self._default_handler.clear(key)
