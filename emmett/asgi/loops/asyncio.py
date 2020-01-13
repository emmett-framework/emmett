# -*- coding: utf-8 -*-
"""
    emmett.asgi.loops.asyncio
    -------------------------

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

import asyncio

from . import loops


@loops.register('asyncio')
def build_asyncio_loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    return loop
