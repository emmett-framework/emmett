# -*- coding: utf-8 -*-
"""
    emmett.asgi.loops.asyncio
    -------------------------

    :copyright: (c) 2014-2019 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

import asyncio

from . import loops


@loops.register('asyncio')
def build_asyncio_loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    return loop
