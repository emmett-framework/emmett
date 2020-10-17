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
    if 'uvloop' in loops:
        return loops.get('uvloop')
    return loops.get('asyncio')
