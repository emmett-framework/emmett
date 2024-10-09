# -*- coding: utf-8 -*-
"""
emmett.asgi.handlers
--------------------

Provides ASGI handlers.

:copyright: 2014 Giovanni Barillari
:license: BSD-3-Clause
"""

from __future__ import annotations

from hashlib import md5
from importlib import resources
from typing import Awaitable, Callable

from emmett_core.http.response import HTTPBytesResponse, HTTPResponse
from emmett_core.protocols.asgi.handlers import HTTPHandler as _HTTPHandler, WSHandler as _WSHandler
from emmett_core.protocols.asgi.typing import Receive, Scope, Send
from emmett_core.utils import cachedprop

from ..ctx import current
from ..debug import debug_handler, smart_traceback
from ..libs.contenttype import contenttype
from ..wrappers.response import Response
from .wrappers import Request, Websocket


class HTTPHandler(_HTTPHandler):
    __slots__ = []
    wrapper_cls = Request
    response_cls = Response

    @cachedprop
    def error_handler(self) -> Callable[[], Awaitable[str]]:
        return self._debug_handler if self.app.debug else self.exception_handler

    async def _static_content(self, content: bytes, content_type: str) -> HTTPBytesResponse:
        content_len = str(len(content))
        return HTTPBytesResponse(
            200,
            content,
            headers={
                "content-type": content_type,
                "content-length": content_len,
                "last-modified": self._internal_assets_md[1],
                "etag": md5(f"{self._internal_assets_md[0]}_{content_len}".encode("utf8")).hexdigest(),
            },
        )

    def _static_handler(self, scope: Scope, receive: Receive, send: Send) -> Awaitable[HTTPResponse]:
        path = scope["emt.path"]
        #: handle internal assets
        if path.startswith("/__emmett__"):
            file_name = path[12:]
            if not file_name or file_name.endswith(".html"):
                return self._http_response(404)
            pkg = None
            if "/" in file_name:
                pkg, file_name = file_name.split("/", 1)
            try:
                file_contents = resources.read_binary(f"emmett.assets.{pkg}" if pkg else "emmett.assets", file_name)
            except FileNotFoundError:
                return self._http_response(404)
            return self._static_content(file_contents, contenttype(file_name))
        return super()._static_handler(scope, receive, send)

    async def _debug_handler(self) -> str:
        current.response.headers._data["content-type"] = "text/html; charset=utf-8"
        return debug_handler(smart_traceback(self.app))


class WSHandler(_WSHandler):
    __slots__ = []
    wrapper_cls = Websocket
