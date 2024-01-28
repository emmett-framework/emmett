# -*- coding: utf-8 -*-
"""
    emmett.rsgi.wrappers
    --------------------

    Provides RSGI request and websocket wrappers

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

import asyncio

from datetime import datetime
from typing import Any, Dict, List, Union, Optional
from urllib.parse import parse_qs

from granian.rsgi import Scope, HTTPProtocol, ProtocolClosed

from .helpers import WSTransport
from ..datastructures import sdict
from ..http import HTTP
from ..utils import cachedprop
from ..wrappers.helpers import regex_client
from ..wrappers.request import Request as _Request
from ..wrappers.websocket import Websocket as _Websocket


class RSGIIngressMixin:
    def __init__(
        self,
        scope: Scope,
        path: str,
        protocol: Union[HTTPProtocol, WSTransport]
    ):
        self._scope = scope
        self._proto = protocol
        self.scheme = scope.scheme
        self.path = path

    @property
    def headers(self):
        return self._scope.headers

    @cachedprop
    def host(self) -> str:
        if self._scope.http_version[0] == '1':
            return self.headers.get('host')
        return self._scope.authority

    @cachedprop
    def query_params(self) -> sdict[str, Union[str, List[str]]]:
        rv: sdict[str, Any] = sdict()
        for key, values in parse_qs(
            self._scope.query_string, keep_blank_values=True
        ).items():
            if len(values) == 1:
                rv[key] = values[0]
                continue
            rv[key] = values
        return rv


class Request(RSGIIngressMixin, _Request):
    __slots__ = ['_scope', '_proto']

    def __init__(
        self,
        scope: Scope,
        path: str,
        protocol: HTTPProtocol,
        max_content_length: Optional[int] = None,
        body_timeout: Optional[int] = None
    ):
        super().__init__(scope, path, protocol)
        self.max_content_length = max_content_length
        self.body_timeout = body_timeout
        self._now = datetime.utcnow()
        self.method = scope.method

    @property
    def _multipart_headers(self):
        return dict(self.headers.items())

    @cachedprop
    async def body(self) -> bytes:
        if (
            self.max_content_length and
            self.content_length > self.max_content_length
        ):
            raise HTTP(413, 'Request entity too large')
        try:
            rv = await asyncio.wait_for(self._proto(), timeout=self.body_timeout)
        except asyncio.TimeoutError:
            raise HTTP(408, 'Request timeout')
        return rv

    @cachedprop
    def client(self) -> str:
        g = regex_client.search(self.headers.get('x-forwarded-for', ''))
        client = (
            (g.group() or '').split(',')[0] if g else (
                self._scope.client[0] if self._scope.client else None
            )
        )
        if client in (None, '', 'unknown', 'localhost'):
            client = '::1' if self.host.startswith('[') else '127.0.0.1'
        return client  # type: ignore

    async def push_promise(self, path: str):
        raise NotImplementedError("RSGI protocol doesn't support HTTP2 push.")


class Websocket(RSGIIngressMixin, _Websocket):
    __slots__ = ['_scope', '_proto']

    def __init__(
        self,
        scope: Scope,
        path: str,
        protocol: WSTransport
    ):
        super().__init__(scope, path, protocol)
        self._flow_receive = None
        self._flow_send = None
        self.receive = self._accept_and_receive
        self.send = self._accept_and_send

    async def accept(
        self,
        headers: Optional[Dict[str, str]] = None,
        subprotocol: Optional[str] = None
    ):
        if self._proto.transport:
            return
        await self._proto.init()
        self.receive = self._wrapped_receive
        self.send = self._wrapped_send

    async def _wrapped_receive(self) -> Any:
        data = (await self._proto.receive()).data
        for method in self._flow_receive:
            data = method(data)
        return data

    async def _wrapped_send(self, data: Any):
        for method in self._flow_send:
            data = method(data)
        trx = (
            self._proto.transport.send_str if isinstance(data, str) else
            self._proto.transport.send_bytes
        )
        try:
            await trx(data)
        except ProtocolClosed:
            if not self._proto.interrupted:
                raise
            await self._proto.noop.wait()
