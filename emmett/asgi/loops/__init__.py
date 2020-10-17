# -*- coding: utf-8 -*-
"""
    emmett.asgi.loops
    -----------------

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

from ..helpers import BuilderRegistry

loops = BuilderRegistry()

from . import (
    asyncio,
    auto,
    uvloop
)
