# -*- coding: utf-8 -*-
"""
    emmett.asgi.loops.auto
    ----------------------

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

from . import loops


@loops.register('auto')
def build_auto_loop():
    if 'uvloop' in loops.builders:
        return loops.get_loop('uvloop')
    return loops.get_loop('asyncio')
