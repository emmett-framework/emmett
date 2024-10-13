# -*- coding: utf-8 -*-
"""
tests.cache
-----------

Test Emmett cache module
"""

import pytest

from emmett import App
from emmett.cache import DiskCache


async def _await_2():
    return 2


async def _await_3():
    return 3


@pytest.mark.asyncio
async def test_diskcache():
    App(__name__)

    disk_cache = DiskCache()
    assert disk_cache._threshold == 500

    assert disk_cache("test", lambda: 2) == 2
    assert disk_cache("test", lambda: 3, 300) == 2

    assert await disk_cache("test_loop", _await_2) == 2
    assert await disk_cache("test_loop", _await_3, 300) == 2

    disk_cache.set("test", 3)
    assert disk_cache.get("test") == 3

    disk_cache.set("test", 4, 300)
    assert disk_cache.get("test") == 4

    disk_cache.clear()
    assert disk_cache.get("test") is None
