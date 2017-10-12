# -*- coding: utf-8 -*-
"""
    tests.cache
    ----------------

    Test weppy cache module

    :copyright: (c) 2014-2016 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""


from weppy.cache import CacheHandler, RamCache, DiskCache, Cache


def test_basecache():
    base_cache = CacheHandler()
    assert base_cache._default_expire == 300

    assert base_cache('key', lambda: 'value') is 'value'
    assert base_cache.get('key') is None
    assert base_cache.set('key', 'value', 300) is None
    assert base_cache.clear() is None


def test_ramcache():
    ram_cache = RamCache()
    assert ram_cache._prefix == ''
    assert ram_cache._threshold == 500

    ram_cache('test', lambda: 2)
    assert ram_cache('test', lambda: 3, 300) == 2

    ram_cache.set('test', 3)
    assert ram_cache.get('test') == 3

    ram_cache.set('test', 4, 300)
    assert ram_cache.get('test') == 4

    ram_cache.clear()
    assert ram_cache.get('test') is None


def test_diskcache():
    disk_cache = DiskCache()
    assert disk_cache._threshold == 500

    disk_cache('test', lambda: 2)
    assert disk_cache('test', lambda: 3, 300) == 2

    disk_cache.set('test', 3)
    assert disk_cache.get('test') == 3

    disk_cache.set('test', 4, 300)
    assert disk_cache.get('test') == 4

    disk_cache.clear()
    assert disk_cache.get('test') is None


def test_cache():
    default_cache = Cache()
    assert isinstance(default_cache._default_handler, RamCache)

    default_cache('test', lambda: 2)
    assert default_cache('test', lambda: 3) == 2
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


def test_cache_decorator():
    cache = Cache(ram=RamCache(prefix='bar:'))

    @cache('foo')
    def foo(*args, **kwargs):
        pass

    #: no arguments
    for _ in range(0, 2):
        foo()
    assert len(cache._default_handler.data.keys()) == 1
    #: args change the cache key
    for _ in range(0, 2):
        foo(1)
    assert len(cache._default_handler.data.keys()) == 2
    for _ in range(0, 2):
        foo(1, 2)
    assert len(cache._default_handler.data.keys()) == 3
    #: kwargs change the cache key
    for _ in range(0, 2):
        foo(1, a='foo', b='bar')
    assert len(cache._default_handler.data.keys()) == 4
    #: kwargs order won't change the cache key
    for _ in range(0, 2):
        foo(1, b='bar', a='foo')
    assert len(cache._default_handler.data.keys()) == 4
