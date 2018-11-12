# -*- coding: utf-8 -*-

from . import loops


@loops.register('auto')
def build_auto_loop():
    if 'uvloop' in loops.builders:
        return loops.get_loop('uvloop')
    return loops.get_loop('asyncio')
