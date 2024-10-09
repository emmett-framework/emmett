# -*- coding: utf-8 -*-
"""
emmett.asgi.wrappers
--------------------

Provides ASGI request and websocket wrappers

:copyright: 2014 Giovanni Barillari
:license: BSD-3-Clause
"""

import pendulum
from emmett_core.protocols.asgi.wrappers import Request as _Request, Websocket as Websocket
from emmett_core.utils import cachedprop


class Request(_Request):
    __slots__ = []

    @cachedprop
    def now(self) -> pendulum.DateTime:
        return pendulum.instance(self._now)

    @cachedprop
    def now_local(self) -> pendulum.DateTime:
        return self.now.in_timezone(pendulum.local_timezone())  # type: ignore
