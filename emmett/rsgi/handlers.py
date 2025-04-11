# -*- coding: utf-8 -*-
"""
emmett.rsgi.handlers
--------------------

Provides RSGI handlers.

:copyright: 2014 Giovanni Barillari
:license: BSD-3-Clause
"""

from __future__ import annotations

import asyncio
import os
from typing import Awaitable, Callable

from emmett_core.http.response import HTTPResponse, HTTPStringResponse
from emmett_core.protocols.rsgi.handlers import HTTPHandler as _HTTPHandler, WSHandler as _WSHandler, WSTransport
from emmett_core.protocols.rsgi.helpers import noop_response
from emmett_core.utils import cachedprop

from ..ctx import RequestContext, WSContext, current
from ..debug import debug_handler, smart_traceback
from .wrappers import Request, Response, Websocket


class HTTPHandler(_HTTPHandler):
    __slots__ = []
    wapper_cls = Request
    response_cls = Response

    @cachedprop
    def error_handler(self) -> Callable[[], Awaitable[str]]:
        return self._debug_handler if self.app.debug else self.exception_handler

    def _static_handler(self, scope, protocol, path: str) -> Awaitable[HTTPResponse]:
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

    async def dynamic_handler(self, scope, protocol, path: str) -> HTTPResponse:
        request = Request(
            scope,
            path,
            protocol,
            max_content_length=self.app.config.request_max_content_length,
            max_multipart_size=self.app.config.request_multipart_max_size,
            body_timeout=self.app.config.request_body_timeout,
        )
        response = Response(protocol)
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
        except asyncio.CancelledError:
            http = noop_response
        except Exception:
            self.app.log.exception("Application exception:")
            http = HTTPStringResponse(500, await self.error_handler(), headers=response.headers)
        finally:
            current._close_(ctx_token)
        return http


class WSHandler(_WSHandler):
    wrapper_cls = Websocket

    async def dynamic_handler(self, scope, transport: WSTransport, path: str):
        ctx = WSContext(self.app, Websocket(scope, path, transport))
        ctx_token = current._init_(ctx)
        try:
            await self.router.dispatch(ctx.websocket)
        except HTTPResponse as http:
            transport.status = http.status_code
        except asyncio.CancelledError:
            if not transport.interrupted:
                self.app.log.exception("Application exception:")
        except Exception:
            transport.status = 500
            self.app.log.exception("Application exception:")
        finally:
            current._close_(ctx_token)
