# -*- coding: utf-8 -*-
"""
    tests.cache
    -----------

    Test Emmett cache module
"""

import pytest

from collections import defaultdict

from emmett import App
from emmett.cache import CacheHandler, RamCache, DiskCache, Cache


def test_basecache():
    base_cache = CacheHandler()
    assert base_cache._default_expire == 300

    assert base_cache('key', lambda: 'value') is 'value'
    assert base_cache.get('key') is None
    assert base_cache.set('key', 'value', 300) is None
    assert base_cache.clear() is None


async def _await_2():
    return 2


async def _await_3():
    return 3


@pytest.mark.asyncio
async def test_ramcache():
    ram_cache = RamCache()
    assert ram_cache._prefix == ''
    assert ram_cache._threshold == 500

    assert ram_cache('test', lambda: 2) == 2
    assert ram_cache('test', lambda: 3, 300) == 2

    assert await ram_cache('test_loop', _await_2) == 2
    assert await ram_cache('test_loop', _await_3, 300) == 2

    ram_cache.set('test', 3)
    assert ram_cache.get('test') == 3

    ram_cache.set('test', 4, 300)
    assert ram_cache.get('test') == 4

    ram_cache.clear()
    assert ram_cache.get('test') is None


@pytest.mark.asyncio
async def test_diskcache():
    App(__name__)

    disk_cache = DiskCache()
    assert disk_cache._threshold == 500

    assert disk_cache('test', lambda: 2) == 2
    assert disk_cache('test', lambda: 3, 300) == 2

    assert await disk_cache('test_loop', _await_2) == 2
    assert await disk_cache('test_loop', _await_3, 300) == 2

    disk_cache.set('test', 3)
    assert disk_cache.get('test') == 3

    disk_cache.set('test', 4, 300)
    assert disk_cache.get('test') == 4

    disk_cache.clear()
    assert disk_cache.get('test') is None


@pytest.mark.asyncio
async def test_cache():
    default_cache = Cache()
    assert isinstance(default_cache._default_handler, RamCache)

    assert default_cache('test', lambda: 2) == 2
    assert default_cache('test', lambda: 3) == 2

    assert await default_cache('test_loop', _await_2) == 2
    assert await default_cache('test_loop', _await_3, 300) == 2

    default_cache.set('test', 3)
    assert default_cache('test', lambda: 2) == 3

    default_cache.set('test', 4, 300)
    assert default_cache('test', lambda: 2, 300) == 4

    default_cache.clear()

    disk_cache = DiskCache()
    ram_cache = RamCache()
    cache = Cache(default='disc', ram=ram_cache, disc=disk_cache)
    assert isinstance(cache._default_handler, DiskCache)
    assert cache.disc == disk_cache
    assert cache.ram == ram_cache


def test_cache_decorator_sync():
    cache = Cache(ram=RamCache(prefix='test:'))
    calls = defaultdict(lambda: 0)

    @cache('foo')
    def foo(*args, **kwargs):
        calls['foo'] += 1
        return 'foo'

    #: no arguments
    for _ in range(0, 2):
        foo()
    assert len(cache._default_handler.data.keys()) == 1
    assert calls['foo'] == 1

    #: args change the cache key
    for _ in range(0, 2):
        foo(1)
    assert len(cache._default_handler.data.keys()) == 2
    assert calls['foo'] == 2

    for _ in range(0, 2):
        foo(1, 2)
    assert len(cache._default_handler.data.keys()) == 3
    assert calls['foo'] == 3

    #: kwargs change the cache key
    for _ in range(0, 2):
        foo(1, a='foo', b='bar')
    assert len(cache._default_handler.data.keys()) == 4
    assert calls['foo'] == 4

    #: kwargs order won't change the cache key
    for _ in range(0, 2):
        foo(1, b='bar', a='foo')
    assert len(cache._default_handler.data.keys()) == 4
    assert calls['foo'] == 4


@pytest.mark.asyncio
async def test_cache_decorator_loop():
    cache = Cache(ram=RamCache(prefix='bar:'))
    calls = defaultdict(lambda: 0)

    @cache('bar')
    async def bar(*args, **kwargs):
        calls['bar'] += 1
        return 'bar'

    #: no arguments
    for _ in range(0, 2):
        await bar()
    assert len(cache._default_handler.data.keys()) == 1
    assert calls['bar'] == 1

    #: args change the cache key
    for _ in range(0, 2):
        await bar(1)
    assert len(cache._default_handler.data.keys()) == 2
    assert calls['bar'] == 2

    for _ in range(0, 2):
        await bar(1, 2)
    assert len(cache._default_handler.data.keys()) == 3
    assert calls['bar'] == 3

    #: kwargs change the cache key
    for _ in range(0, 2):
        await bar(1, a='foo', b='bar')
    assert len(cache._default_handler.data.keys()) == 4
    assert calls['bar'] == 4

    #: kwargs order won't change the cache key
    for _ in range(0, 2):
        await bar(1, b='bar', a='foo')
    assert len(cache._default_handler.data.keys()) == 4
    assert calls['bar'] == 4
