# -*- coding: utf-8 -*-
"""
emmett.rsgi.wrappers
--------------------

Provides RSGI request and websocket wrappers

:copyright: 2014 Giovanni Barillari
:license: BSD-3-Clause
"""

import pendulum
from emmett_core.protocols.rsgi.wrappers import Request as _Request, Response as _Response, Websocket as Websocket
from emmett_core.utils import cachedprop

from ..wrappers.response import ResponseMixin


class Request(_Request):
    __slots__ = []

    @cachedprop
    def now(self) -> pendulum.DateTime:
        return pendulum.instance(self._now)

    @cachedprop
    def now_local(self) -> pendulum.DateTime:
        return self.now.in_timezone(pendulum.local_timezone())  # type: ignore


class Response(ResponseMixin, _Response):
    __slots__ = []
