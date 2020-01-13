# -*- coding: utf-8 -*-
"""
    emmett.asgi.loops
    -----------------

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

from ..helpers import BuilderRegistry


class LoopRegistry(BuilderRegistry):
    def get_loop(self, name):
        try:
            builder, packages = self.builders[name]
        except KeyError:
            raise RuntimeError(
                'Event loop implementation "{}" not available'.format(name)
            )
        return builder(**packages)


loops = LoopRegistry()

from . import (
    asyncio,
    auto,
    uvloop
)
