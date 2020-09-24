# -*- coding: utf-8 -*-
"""
    emmett.cache
    ------------

    Provides a caching system.

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

from __future__ import annotations

import asyncio
import heapq
import os
import pickle
import tempfile
import threading
import time

from collections import OrderedDict
from functools import wraps
from typing import (
    Any, Awaitable, Callable, Dict, List, Optional, Tuple, Union, overload
)

from ._shortcuts import hashlib_sha1
from .ctx import current
from .libs.portalocker import LockedFile
from .typing import T

__all__ = ['Cache']


class CacheHashMixin:
    def __init__(self):
        self.strategies = OrderedDict()

    def add_strategy(
        self,
        key: str,
        method: Callable[..., Any] = lambda data: data
    ):
        self.strategies[key] = method

    def _hash_component(self, key: str, data: Any) -> str:
        return ''.join([key, "{", repr(data), "}"])

    def _build_hash(self, data: Dict[str, Any]) -> str:
        components = []
        for key, strategy in self.strategies.items():
            components.append(self._hash_component(key, strategy(data[key])))
        return hashlib_sha1(':'.join(components)).hexdigest()

    def _build_ctx_key(self, **ctx) -> str:
        return self.key + ":" + self._build_hash(ctx)  # type: ignore  # noqa

    @staticmethod
    def dict_strategy(data: Dict[str, Any]) -> List[Tuple[str, Any]]:
        return [(key, data[key]) for key in sorted(data)]


class CacheHandler:
    def __init__(self, prefix: str = '', default_expire: int = 300):
        self._default_expire = default_expire
        self._prefix = prefix

    @staticmethod
    def _key_prefix_(method: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(method)
        def wrap(self, key: Optional[str] = None, *args, **kwargs) -> Any:
            key = self._prefix + key if key is not None else key
            return method(self, key, *args, **kwargs)
        return wrap

    @staticmethod
    def _convert_duration_(method: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(method)
        def wrap(
            self,
            key: str,
            value: Any,
            duration: Union[int, str, None] = 'default'
        ) -> Any:
            if duration is None:
                duration = 60 * 60 * 24 * 365
            if duration == "default":
                duration = self._default_expire
            now = time.time()
            return method(
                self, key, value,
                now=now,
                duration=duration,
                expiration=now + duration  # type: ignore
            )
        return wrap

    @overload
    def __call__(
        self,
        key: Optional[str] = None,
        function: None = None,
        duration: Union[int, str, None] = 'default'
    ) -> CacheDecorator:
        ...

    @overload
    def __call__(
        self,
        key: str,
        function: Optional[Callable[..., T]],
        duration: Union[int, str, None] = 'default'
    ) -> T:
        ...

    def __call__(
        self,
        key: Optional[str] = None,
        function: Optional[Callable[..., T]] = None,
        duration: Union[int, str, None] = 'default'
    ) -> Union[CacheDecorator, T]:
        if function:
            if asyncio.iscoroutinefunction(function):
                return self.get_or_set_loop(key, function, duration)  # type: ignore
            return self.get_or_set(key, function, duration)  # type: ignore
        return CacheDecorator(self, key, duration)

    def get_or_set(
        self,
        key: str,
        function: Callable[[], T],
        duration: Union[int, str, None] = 'default'
    ) -> T:
        value = self.get(key)
        if value is None:
            value = function()
            self.set(key, value, duration)
        return value

    async def get_or_set_loop(
        self,
        key: str,
        function: Callable[[], T],
        duration: Union[int, str, None] = 'default'
    ) -> T:
        value = self.get(key)
        if value is None:
            value = await function()  # type: ignore
            self.set(key, value, duration)
        return value

    def get(self, key: str) -> Any:
        return None

    def set(self, key: str, value: Any, duration: Union[int, str, None]):
        pass

    def clear(self, key: Optional[str] = None):
        pass

    def response(
        self,
        duration: Union[int, str, None] = 'default',
        query_params: bool = True,
        language: bool = True,
        hostname: bool = False,
        headers: List[str] = []
    ) -> RouteCacheRule:
        return RouteCacheRule(
            self, query_params, language, hostname, headers, duration
        )


class CacheDecorator(CacheHashMixin):
    def __init__(
        self,
        handler: CacheHandler,
        key: Optional[str],
        duration: Union[int, str, None] = 'default'
    ):
        super().__init__()
        self._cache = handler
        self.key = key
        self.duration = duration
        self.add_strategy('args')
        self.add_strategy('kwargs', self.dict_strategy)

    def _key_from_wrapped(self, f: Callable[..., Any]) -> str:
        return f.__module__ + '.' + f.__name__

    def _wrap_sync(self, f: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(f)
        def wrap(*args, **kwargs) -> Any:
            if not args and not kwargs:
                key = self.key or self._key_from_wrapped(f)
            else:
                key = self._build_ctx_key(args=args, kwargs=kwargs)
            return self._cache.get_or_set(
                key, lambda: f(*args, **kwargs), self.duration
            )
        return wrap

    def _wrap_loop(
        self,
        f: Callable[..., Awaitable[Any]]
    ) -> Callable[..., Awaitable[Any]]:
        @wraps(f)
        async def wrap(*args, **kwargs) -> Any:
            if not args and not kwargs:
                key = self.key or self._key_from_wrapped(f)
            else:
                key = self._build_ctx_key(args=args, kwargs=kwargs)
            return await self._cache.get_or_set_loop(
                key, lambda: f(*args, **kwargs), self.duration
            )
        return wrap

    def __call__(self, f: Callable[..., Any]) -> Callable[..., Any]:
        rv = (
            self._wrap_loop(f) if asyncio.iscoroutinefunction(f) else
            self._wrap_sync(f)
        )
        if not self.key:
            self.key = f.__module__ + '.' + f.__name__
        return rv


class RamElement:
    __slots__ = ('value', 'exp', 'acc')

    def __init__(self, value: Any, exp: int, acc: int):
        self.value = value
        self.exp = exp
        self.acc = acc


class RamCache(CacheHandler):
    lock = threading.RLock()

    def __init__(
        self,
        prefix: str = '',
        threshold: int = 500,
        default_expire: int = 300
    ):
        super().__init__(
            prefix=prefix, default_expire=default_expire)
        self.data: Dict[str, Any] = {}
        self._heap_exp: List[Tuple[int, str]] = []
        self._heap_acc: List[Tuple[float, str]] = []
        self._threshold = threshold

    def _prune(self, now):
        # remove expired items
        while self._heap_exp:
            exp, rk = self._heap_exp[0]
            if exp >= now:
                break
            self._heap_exp.remove((exp, rk))
            element = self.data.get(rk)
            if element and element.exp == exp:
                self._heap_acc.remove((self.data[rk].acc, rk))
                del self.data[rk]
        # remove threshold exceding elements
        while len(self.data) > self._threshold:
            rk = heapq.heappop(self._heap_acc)[1]
            element = self.data.get(rk)
            if element:
                self._heap_exp.remove((element.exp, rk))
                del self.data[rk]

    @CacheHandler._key_prefix_
    def get(self, key: str) -> Any:
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
    def set(self, key: str, value: Any, **kwargs):
        with self.lock:
            self._prune(kwargs['now'])
            heapq.heappush(self._heap_exp, (kwargs['expiration'], key))
            heapq.heappush(self._heap_acc, (kwargs['now'], key))
            self.data[key] = RamElement(
                value, kwargs['expiration'], kwargs['now'])

    @CacheHandler._key_prefix_
    def clear(self, key: Optional[str] = None):
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
    _fs_transaction_suffix = '.__mt_cache'
    _fs_mode = 0o600

    def __init__(
        self,
        cache_dir: str = 'cache',
        threshold: int = 500,
        default_expire: int = 300
    ):
        super().__init__(default_expire=default_expire)
        self._threshold = threshold
        self._path = os.path.join(current.app.root_path, cache_dir)
        #: create required paths if needed
        if not os.path.exists(self._path):
            os.mkdir(self._path)

    def _get_filename(self, key: str) -> str:
        khash = hashlib_sha1(key).hexdigest()
        return os.path.join(self._path, khash)

    def _del_file(self, filename: str):
        try:
            os.remove(filename)
        except Exception:
            pass

    def _list_dir(self) -> List[str]:
        return [
            os.path.join(self._path, fn)
            for fn in os.listdir(self._path)
            if not fn.endswith(self._fs_transaction_suffix)
        ]

    def _prune(self):
        with self.lock:
            entries = self._list_dir()
            if len(entries) > self._threshold:
                now = time.time()
                try:
                    for i, fpath in enumerate(entries):
                        remove = False
                        f = LockedFile(fpath, 'rb')
                        exp = pickle.load(f.file)
                        f.close()
                        remove = exp <= now or i % 3 == 0
                        if remove:
                            self._del_file(fpath)
                except Exception:
                    pass

    def get(self, key: str) -> Any:
        filename = self._get_filename(key)
        try:
            with self.lock:
                now = time.time()
                f = LockedFile(filename, 'rb')
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
    def set(self, key: str, value: Any, **kwargs):
        filename = self._get_filename(key)
        filepath = os.path.join(self._path, filename)
        with self.lock:
            self._prune()
            if os.path.exists(filepath):
                self._del_file(filepath)
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

    def clear(self, key: Optional[str] = None):
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
        self,
        host: str = 'localhost',
        port: int = 6379,
        password: Optional[str] = None,
        db: int = 0,
        prefix: str = 'cache:',
        default_expire: int = 300,
        **kwargs
    ):
        super().__init__(
            prefix=prefix, default_expire=default_expire)
        try:
            import redis
        except ImportError:
            raise RuntimeError('no redis module found')
        self._cache = redis.Redis(
            host=host, port=port, password=password, db=db, **kwargs
        )

    def _dump_obj(self, value: Any) -> bytes:
        if isinstance(value, int):
            return str(value).encode('ascii')
        return b'!' + pickle.dumps(value)

    def _load_obj(self, value: Any) -> Any:
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
    def get(self, key: str) -> Any:
        return self._load_obj(self._cache.get(key))

    @CacheHandler._key_prefix_
    @CacheHandler._convert_duration_
    def set(self, key: str, value: Any, **kwargs):
        dumped = self._dump_obj(value)
        return self._cache.setex(
            name=key,
            time=kwargs['duration'],
            value=dumped
        )

    @CacheHandler._key_prefix_
    def clear(self, key: Optional[str] = None):
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


class RouteCacheRule(CacheHashMixin):
    def __init__(
        self,
        handler: CacheHandler,
        query_params: bool = True,
        language: bool = True,
        hostname: bool = False,
        headers: List[str] = [],
        duration: Union[int, str, None] = 'default'
    ):
        super().__init__()
        self.cache = handler
        self.check_headers = headers
        self.duration = duration
        self.add_strategy('kwargs', self.dict_strategy)
        self._ctx_builders = []
        if hostname:
            self.add_strategy('hostname')
            self._ctx_builders.append(
                ('hostname', lambda route, current: route.hostname))
        if language:
            self.add_strategy('language')
            self._ctx_builders.append(
                ('language', lambda route, current: current.language))
        if query_params:
            self.add_strategy('query_params', self.dict_strategy)
            self._ctx_builders.append(
                ('query_params', lambda route, current:
                    current.request.query_params))
        if headers:
            self.add_strategy('headers', self.headers_strategy)
            self._ctx_builders.append(
                ('headers', lambda route, current: current.request.headers))

    def _build_ctx_key(self, route: Any, **ctx) -> str:  # type: ignore
        return route.name + ":" + self._build_hash(ctx)

    def _build_ctx(
        self,
        kwargs: Dict[str, Any],
        route: Any,
        current: Any
    ) -> Dict[str, Any]:
        rv = {'kwargs': kwargs}
        for key, builder in self._ctx_builders:
            rv[key] = builder(route, current)
        return rv

    def headers_strategy(self, data: Dict[str, str]) -> List[str]:
        return [data[key] for key in self.check_headers]

    def __call__(self, f: Callable[..., Any]) -> Callable[..., Any]:
        from .routing.router import Router
        obj = Router.exposing()
        obj.cache_rule = self
        return f


class Cache:
    def __init__(self, **kwargs):
        #: load handlers
        handlers = []
        for key, val in kwargs.items():
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

    @overload
    def __call__(
        self,
        key: Optional[str] = None,
        function: None = None,
        duration: Union[int, str, None] = 'default'
    ) -> CacheDecorator:
        ...

    @overload
    def __call__(
        self,
        key: str,
        function: Optional[Callable[..., T]],
        duration: Union[int, str, None] = 'default'
    ) -> T:
        ...

    def __call__(
        self,
        key: Optional[str] = None,
        function: Optional[Callable[..., T]] = None,
        duration: Union[int, str, None] = 'default'
    ) -> Union[CacheDecorator, T]:
        return self._default_handler(key, function, duration)

    def get(self, key: str) -> Any:
        return self._default_handler.get(key)

    def set(
        self,
        key: str,
        value: Any,
        duration: Union[int, str, None] = 'default'
    ):
        self._default_handler.set(key, value, duration)

    def get_or_set(
        self,
        key: str,
        function: Callable[..., T],
        duration: Union[int, str, None] = 'default'
    ) -> T:
        return self._default_handler.get_or_set(key, function, duration)

    def clear(self, key: Optional[str] = None):
        self._default_handler.clear(key)

    def response(
        self,
        duration: Union[int, str, None] = 'default',
        query_params: bool = True,
        language: bool = True,
        hostname: bool = False,
        headers: List[str] = []
    ) -> RouteCacheRule:
        return self._default_handler.response(
            duration, query_params, language, hostname, headers
        )
