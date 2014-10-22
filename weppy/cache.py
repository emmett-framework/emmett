# -*- coding: utf-8 -*-
"""
    weppy.cache
    -----------

    Provides a caching system.

    :copyright: (c) 2014 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

import os
import time
import heapq
import threading
import tempfile
from hashlib import md5

from ._compat import pickle, integer_types

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
    _heap_exp = []
    _heap_acc = []
    _fs_transaction_suffix = '.__wp_cache'
    _fs_mode = 0o600

    def __init__(self, cache_dir='cache', threshold=500, default_expire=300):
        BaseCache.__init__(self, default_expire)
        self._threshold = threshold
        from .expose import Expose
        self._path = os.path.join(Expose.application.root_path, cache_dir)
        self._map_file = os.path.join(self._path, '__map_wp_cache')
        #: create required paths if needed
        if not os.path.exists(self._path):
            os.mkdir(self._path)
        if not os.path.exists(self._map_file):
            self._init_acc()

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
                    with open(filename, 'rb') as f:
                        exp = pickle.load(f)
                    acc = self._get_acc(key)
                    self._del_acc(key)
                    self._heap_acc.remove((acc, key))
                    self._heap_exp.remove((exp, key))
                    os.remove(filename)
                    return
                except:
                    return
            for name in self._list_dir():
                self._del_file(name)
            self._heap_acc = []
            self._heap_exp = []
            self._init_acc()

    def _list_dir(self):
        return [os.path.join(self._path, fn) for fn in os.listdir(self._path)
                if not fn.endswith(self._fs_transaction_suffix)]

    def _prune(self):
        now = time.time()
        # remove expired items
        while self._heap_exp:
            exp, rk = heapq.heappop(self._heap_exp)
            if exp < now:
                filename = self._get_filename(rk)
                acc = self._get_acc(rk)
                self._del_acc(rk)
                self._heap_acc.remove((acc, rk))
                self._del_file(filename)
            else:
                heapq.heappush(self._heap_exp, (exp, rk))
                break
        # remove threshold exceding elements
        while len(self._list_dir()) > self._threshold:
            rk = heapq.heappop(self._heap_acc)[1]
            filename = self._get_filename(rk)
            try:
                self._del_acc(rk)
                with open(filename, 'rb') as f:
                    exp = pickle.load(f)
                self._heap_exp.remove((exp, rk))
                os.remove(filename)
            except:
                pass

    def _get_filename(self, key):
        if isinstance(key, unicode):
            key = key.encode('utf-8')
        khash = md5(key).hexdigest()
        return os.path.join(self._path, khash)

    def _del_file(self, filename):
        try:
            os.remove(filename)
        except:
            pass

    def _init_acc(self):
        with open(self._map_file, 'wb') as f:
            pickle.dump({}, f, pickle.HIGHEST_PROTOCOL)

    def _get_acc(self, key=None):
        with open(self._map_file, 'rb') as f:
            data = pickle.load(f)
        if key is not None:
            return data[key]
        return data

    def _write_acc(self, data):
        with open(self._map_file, 'wb') as f:
            pickle.dump(data, f, pickle.HIGHEST_PROTOCOL)

    def _set_acc(self, key, acc):
        data = self._get_acc()
        data[key] = acc
        self._write_acc(data)

    def _del_acc(self, key):
        data = self._get_acc()
        del data[key]
        self._write_acc(data)

    def _get(self, key):
        filename = self._get_filename(key)
        try:
            with self.lock:
                now = time.time()
                with open(filename, 'rb') as f:
                    exp = pickle.load(f)
                    if exp < now:
                        return None
                    val = pickle.load(f)
                    acc = self._get_acc(key)
                    self._heap_acc.remove((acc, key))
                    self._set_acc(key, now)
                    heapq.heappush(self._heap_acc, (now, key))
        except:
            return None
        return val

    def _set(self, key, value, dt):
        filename = self._get_filename(key)
        with self.lock:
            self._prune()
            now = time.time()
            try:
                fd, tmp = tempfile.mkstemp(suffix=self._fs_transaction_suffix,
                                           dir=self._path)
                with os.fdopen(fd, 'wb') as f:
                    pickle.dump(int(now + dt), f, 1)
                    pickle.dump(value, f, pickle.HIGHEST_PROTOCOL)
                os.rename(tmp, filename)
                os.chmod(filename, self._fs_mode)
                self._set_acc(key, now)
                heapq.heappush(self._heap_exp, (dt, key))
                heapq.heappush(self._heap_acc, (now, key))
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
            self._client.delete(key)
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
    def __init__(self, handlers=[('ram', RamCache())], default=None):
        for name, handler in handlers:
            setattr(self, name, handler)
        self.default_handler = default or handlers[0][0]

    def __call__(self, key, f, time_expire=None):
        return self.__getattribute__(self.default_handler)(key, f, time_expire)
