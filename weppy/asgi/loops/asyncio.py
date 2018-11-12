# -*- coding: utf-8 -*-

import asyncio

from . import loops


@loops.register('asyncio')
def build_asyncio_loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    return loop
