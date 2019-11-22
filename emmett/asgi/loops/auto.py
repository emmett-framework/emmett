# -*- coding: utf-8 -*-
"""
    emmett.asgi.loops.auto
    ----------------------

    :copyright: (c) 2014-2019 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

from . import loops


@loops.register('auto')
def build_auto_loop():
    if 'uvloop' in loops.builders:
        return loops.get_loop('uvloop')
    return loops.get_loop('asyncio')
