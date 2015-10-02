# -*- coding: utf-8 -*-
"""
    weppy.cache
    -----------

    Provides a caching system.

    :copyright: (c) 2015 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

import os
import time
import heapq
import threading
import tempfile

from ._compat import pickle, integer_types, iteritems, hashlib_md5
from .libs.portalocker import LockedFile

__all__ = ['Cache']


class BaseCache(object):
    def __init__(self, default_expire=300):
        self._default_expire = default_expire

    def __call__(self, key, function=None, dt='default'):
        return self._get(key)

    def _get(self, key):
        return None

    def _set(self, key, value, dt):
        return

    def clear(self, key=None):
        return

    #def inc(self, key, dt=1):
    #    return
    #
    #def dec(self, key, dt=1):
    #    return


class RamElement(object):
    def __init__(self, value, exp, acc):
        self.value = value
        self.exp = exp
        self.acc = acc


class RamCache(BaseCache):
    lock = threading.RLock()
    map = {}
    _heap_exp = []
    _heap_acc = []

    def __init__(self, prefix='', threshold=500, default_expire=300):
        BaseCache.__init__(self, default_expire)
        self._prefix = prefix
        self._threshold = threshold

    def __call__(self, key, function=None, dt='default'):
        key = self._prefix + key
        now = time.time()
        if dt is None:
            dt = 60*60*24*365
        if dt == "default":
            dt = self._default_expire
        if function:
            value = self._get(key)
            if value is None:
                value = function()
                expiration = now + dt
                self._set(key, value, expiration)
            return value
        return None

    def clear(self, key=None):
        with self.lock:
            if key is not None:
                key = self._prefix + key
                try:
                    rv = self.map[key]
                    self._heap_acc.remove((rv.acc, key))
                    self._heap_exp.remove((rv.exp, key))
                    del self.map[key]
                    return
                except:
                    return
            self.map.clear()
            self._heap_acc = []
            self._heap_exp = []

    def _prune(self):
        now = time.time()
        # remove expired items
        while self._heap_exp:
            exp, rk = heapq.heappop(self._heap_exp)
            if exp < now:
                self._heap_acc.remove((self.map[rk].acc, rk))
                del self.map[rk]
            else:
                heapq.heappush(self._heap_exp, (exp, rk))
                break
        # remove threshold exceding elements
        while len(self.map) > self._threshold:
            rk = heapq.heappop(self._heap_acc)[1]
            self._heap_exp.remove((self.map[rk].exp, rk))
            del self.map[rk]

    def _get(self, key):
        try:
            with self.lock:
                element = self.map[key]
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

    def _set(self, key, value, dt):
        with self.lock:
            self._prune()
            now = time.time()
            heapq.heappush(self._heap_exp, (dt, key))
            heapq.heappush(self._heap_acc, (now, key))
            self.map[key] = RamElement(value, dt, now)


class DiskCache(BaseCache):
    lock = threading.RLock()
    _fs_transaction_suffix = '.__wp_cache'
    _fs_mode = 0o600

    def __init__(self, cache_dir='cache', threshold=500, default_expire=300):
        BaseCache.__init__(self, default_expire)
        self._threshold = threshold
        from .expose import Expose
        self._path = os.path.join(Expose.application.root_path, cache_dir)
        #: create required paths if needed
        if not os.path.exists(self._path):
            os.mkdir(self._path)

    def __call__(self, key, function=None, dt='default'):
        now = time.time()
        if dt is None:
            dt = 60*60*24*365
        if dt == "default":
            dt = self._default_expire
        if function:
            value = self._get(key)
            if value is None:
                value = function()
                expiration = now + dt
                self._set(key, value, expiration)
            return value
        return None

    def clear(self, key=None):
        with self.lock:
            if key is not None:
                filename = self._get_filename(key)
                try:
                    os.remove(filename)
                    return
                except:
                    return
            for name in self._list_dir():
                self._del_file(name)

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
                except:
                    pass

    def _get_filename(self, key):
        khash = hashlib_md5(key).hexdigest()
        return os.path.join(self._path, khash)

    def _del_file(self, filename):
        try:
            os.remove(filename)
        except:
            pass

    def _get(self, key):
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
        except:
            return None
        return val

    def _set(self, key, value, exp):
        filename = self._get_filename(key)
        with self.lock:
            self._prune()
            try:
                fd, tmp = tempfile.mkstemp(suffix=self._fs_transaction_suffix,
                                           dir=self._path)
                with os.fdopen(fd, 'wb') as f:
                    pickle.dump(exp, f, 1)
                    pickle.dump(value, f, pickle.HIGHEST_PROTOCOL)
                os.rename(tmp, filename)
                os.chmod(filename, self._fs_mode)
            except:
                pass


class RedisCache(BaseCache):
    def __init__(self, host='localhost', port=6379, password=None,
                 db=0, default_expire=300, prefix='', **kwargs):
        BaseCache.__init__(self, default_expire=default_expire)
        try:
            import redis
        except ImportError:
            raise RuntimeError('no redis module found')
        self._cache = redis.Redis(host=host, port=port, password=password,
                                  db=db, **kwargs)
        self._prefix = prefix

    def __call__(self, key, function=None, dt='default'):
        key = self._prefix + key
        if dt is None:
            dt = 60*60*24*365
        if dt == "default":
            dt = self._default_expire
        if function:
            value = self._get(key)
            if value is None:
                value = function()
                self._set(key, value, dt)
            return value
        return None

    def clear(self, key=None):
        if key is not None:
            key = self._prefix + key
            self._cache.delete(key)
            return
        if self._prefix:
            keys = self._cache.keys(self._prefix + '*')
            if keys:
                self._cache.delete(*keys)
        else:
            self._cache.flushdb()

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

    def _get(self, key):
        return self._load_obj(self._cache.get(key))

    def _set(self, key, value, dt):
        dumped = self._dump_obj(value)
        return self._cache.setex(name=key, value=dumped, time=dt)


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
        self.default_handler = kwargs.get('default', handlers[0][0])

    def __call__(self, key, f, time_expire=None):
        return self.__getattribute__(self.default_handler)(key, f, time_expire)
