# -*- coding: utf-8 -*-
"""
    weppy.asgi.loops
    ----------------

    :copyright: (c) 2014-2019 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
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
