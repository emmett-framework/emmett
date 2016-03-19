# -*- coding: utf-8 -*-
"""
    tests.cache
    ----------------

    Test weppy cache module

    :copyright: (c) 2014-2016 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""


from weppy.cache import BaseCache, RamCache, DiskCache, Cache


def test_basecache():
    base_cache = BaseCache()
    assert base_cache._default_expire == 300

    assert base_cache('key') is None
    assert base_cache._get('key') is None
    assert base_cache._set('key', 'value', 300) is None
    assert base_cache.clear() is None


def test_ramcache():
    ram_cache = RamCache()
    assert ram_cache._prefix == ''
    assert ram_cache._threshold == 500

    ram_cache('test', lambda: 2)
    assert ram_cache._get('test') == 2

    ram_cache.clear()
    assert ram_cache._get('test') is None


def test_diskcache():
    disk_cache = DiskCache()
    assert disk_cache._threshold == 500

    disk_cache('test', lambda: 2)
    assert disk_cache._get('test') == 2

    disk_cache.clear()
    assert disk_cache._get('test') is None


def test_cache():
    default_cache = Cache()
    assert default_cache.default_handler == 'ram'

    default_cache('test', lambda: 2)
    assert default_cache('test', lambda: 3) == 2

    disk_cache = DiskCache()
    ram_cache = RamCache()
    cache = Cache(default='disc', ram=ram_cache, disc=disk_cache)
    assert cache.default_handler == 'disc'
    assert cache.disc == disk_cache
    assert cache.ram == ram_cache
