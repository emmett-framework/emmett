# -*- coding: utf-8 -*-
"""
    weppy.asgi.loops.uvloop
    -----------------------

    :copyright: (c) 2014-2019 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

import asyncio

from . import loops


@loops.register('uvloop', packages=['uvloop'])
def build_uv_loop(uvloop):
    asyncio.get_event_loop().close()
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    return asyncio.get_event_loop()
