# -*- coding: utf-8 -*-

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
