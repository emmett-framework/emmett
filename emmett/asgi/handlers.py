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

from emmett_core.http.response import HTTPBytesResponse, HTTPResponse, HTTPStringResponse
from emmett_core.protocols.asgi.handlers import HTTPHandler as _HTTPHandler, RequestCancelled, WSHandler as _WSHandler
from emmett_core.protocols.asgi.typing import Receive, Scope, Send
from emmett_core.utils import cachedprop

from ..ctx import RequestContext, WSContext, current
from ..debug import debug_handler, smart_traceback
from ..libs.contenttype import contenttype
from .wrappers import Request, Response, Websocket


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

    async def dynamic_handler(self, scope: Scope, receive: Receive, send: Send) -> HTTPResponse:
        request = Request(
            scope,
            receive,
            send,
            max_content_length=self.app.config.request_max_content_length,
            max_multipart_size=self.app.config.request_multipart_max_size,
            body_timeout=self.app.config.request_body_timeout,
        )
        response = Response(send)
        ctx = RequestContext(self.app, request, response)
        ctx_token = current._init_(ctx)
        try:
            http = await self.router.dispatch(request, response)
        except HTTPResponse as http_exception:
            http = http_exception
            #: render error with handlers if in app
            error_handler = self.app.error_handlers.get(http.status_code)
            if error_handler:
                http = HTTPStringResponse(
                    http.status_code, await error_handler(), headers=response.headers, cookies=response.cookies
                )
        except RequestCancelled:
            raise
        except Exception:
            self.app.log.exception("Application exception:")
            http = HTTPStringResponse(500, await self.error_handler(), headers=response.headers)
        finally:
            current._close_(ctx_token)
        return http

    async def _exception_handler(self) -> str:
        current.response.headers._data["content-type"] = "text/plain"
        return "Internal error"


class WSHandler(_WSHandler):
    __slots__ = []
    wrapper_cls = Websocket

    async def dynamic_handler(self, scope: Scope, send: Send):
        ctx = WSContext(self.app, Websocket(scope, scope["emt.input"].get, send))
        ctx_token = current._init_(ctx)
        try:
            await self.router.dispatch(ctx.websocket)
        finally:
            if not scope.get("emt._flow_cancel", False) and ctx.websocket._accepted:
                await send({"type": "websocket.close", "code": 1000})
                scope["emt._ws_closed"] = True
            current._close_(ctx_token)
