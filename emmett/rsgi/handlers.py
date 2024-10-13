# -*- coding: utf-8 -*-
"""
emmett.rsgi.handlers
--------------------

Provides RSGI handlers.

:copyright: 2014 Giovanni Barillari
:license: BSD-3-Clause
"""

from __future__ import annotations

import os
from typing import Awaitable, Callable

from emmett_core.http.response import HTTPResponse
from emmett_core.protocols.rsgi.handlers import HTTPHandler as _HTTPHandler, WSHandler as _WSHandler
from emmett_core.utils import cachedprop
from granian.rsgi import (
    HTTPProtocol,
    Scope,
)

from ..ctx import current
from ..debug import debug_handler, smart_traceback
from ..wrappers.response import Response
from .wrappers import Request, Websocket


class HTTPHandler(_HTTPHandler):
    __slots__ = []
    wapper_cls = Request
    response_cls = Response

    @cachedprop
    def error_handler(self) -> Callable[[], Awaitable[str]]:
        return self._debug_handler if self.app.debug else self.exception_handler

    def _static_handler(self, scope: Scope, protocol: HTTPProtocol, path: str) -> Awaitable[HTTPResponse]:
        #: handle internal assets
        if path.startswith("/__emmett__"):
            file_name = path[12:]
            if not file_name:
                return self._http_response(404)
            static_file = os.path.join(os.path.dirname(__file__), "..", "assets", file_name)
            if os.path.splitext(static_file)[1] == "html":
                return self._http_response(404)
            return self._static_response(static_file)
        #: handle app assets
        static_file, _ = self.static_matcher(path)
        if static_file:
            return self._static_response(static_file)
        return self.dynamic_handler(scope, protocol, path)

    async def _debug_handler(self) -> str:
        current.response.headers._data["content-type"] = "text/html; charset=utf-8"
        return debug_handler(smart_traceback(self.app))


class WSHandler(_WSHandler):
    wrapper_cls = Websocket
