# -*- coding: utf-8 -*-
"""
    emmett.asgi.wrappers
    --------------------

    Provides ASGI request and websocket wrappers

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

import asyncio

from datetime import datetime
from typing import Any, Callable, Dict, Iterator, List, Mapping, Optional, Tuple, Union
from urllib.parse import parse_qs

from ..datastructures import sdict
from ..http import HTTP
from ..utils import cachedprop
from ..wrappers.helpers import regex_client
from ..wrappers.request import Request as _Request
from ..wrappers.websocket import Websocket as _Websocket
from .helpers import RequestCancelled
from .typing import Scope, Receive, Send

_push_headers = {
    "accept",
    "accept-encoding",
    "accept-language",
    "cache-control",
    "user-agent"
}


class Headers(Mapping[str, str]):
    __slots__ = ["_data"]

    def __init__(self, scope: Dict[str, Any]):
        self._data: Dict[bytes, bytes] = {
            key: val for key, val in scope["headers"]
        }

    __hash__ = None  # type: ignore

    def __getitem__(self, key: str) -> str:
        return self._data[key.lower().encode("latin-1")].decode("latin-1")

    def __contains__(self, key: str) -> bool:  # type: ignore
        return key.lower().encode("latin-1") in self._data

    def __iter__(self) -> Iterator[str]:
        for key in self._data.keys():
            yield key.decode("latin-1")

    def __len__(self) -> int:
        return len(self._data)

    def get(
        self,
        key: str,
        default: Optional[Any] = None,
        cast: Optional[Callable[[Any], Any]] = None
    ) -> Any:
        rv = self._data.get(key.lower().encode("latin-1"))
        rv = rv.decode() if rv is not None else default  # type: ignore
        if cast is None:
            return rv
        try:
            return cast(rv)
        except ValueError:
            return default

    def items(self) -> Iterator[Tuple[str, str]]:  # type: ignore
        for key, value in self._data.items():
            yield key.decode("latin-1"), value.decode("latin-1")

    def keys(self) -> Iterator[str]:  # type: ignore
        for key in self._data.keys():
            yield key.decode("latin-1")

    def values(self) -> Iterator[str]:  # type: ignore
        for value in self._data.values():
            yield value.decode("latin-1")


class Body:
    __slots__ = ('_data', '_receive', '_max_content_length')

    def __init__(self, receive, max_content_length=None):
        self._data = bytearray()
        self._receive = receive
        self._max_content_length = max_content_length

    def append(self, data: bytes):
        if data == b'':
            return
        self._data.extend(data)
        if (
            self._max_content_length is not None and
            len(self._data) > self._max_content_length
        ):
            raise HTTP(413, 'Request entity too large')

    async def __load(self) -> bytes:
        while True:
            event = await self._receive()
            if event['type'] == 'http.request':
                self.append(event['body'])
                if not event.get('more_body', False):
                    break
            elif event['type'] == 'http.disconnect':
                raise RequestCancelled
        return bytes(self._data)

    def __await__(self):
        return self.__load().__await__()


class ASGIIngressMixin:
    def __init__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send
    ):
        self._scope = scope
        self._receive = receive
        self._send = send
        self.scheme = scope['scheme']
        self.path = scope['emt.path']

    @cachedprop
    def headers(self) -> Headers:
        return Headers(self._scope)

    @cachedprop
    def query_params(self) -> sdict[str, Union[str, List[str]]]:
        rv: sdict[str, Any] = sdict()
        for key, values in parse_qs(
            self._scope['query_string'].decode('latin-1'), keep_blank_values=True
        ).items():
            if len(values) == 1:
                rv[key] = values[0]
                continue
            rv[key] = values
        return rv

    @cachedprop
    def client(self) -> str:
        g = regex_client.search(self.headers.get('x-forwarded-for', ''))
        client = (
            (g.group() or '').split(',')[0] if g else (
                self._scope['client'][0] if self._scope['client'] else None
            )
        )
        if client in (None, '', 'unknown', 'localhost'):
            client = '::1' if self.host.startswith('[') else '127.0.0.1'
        return client  # type: ignore


class Request(ASGIIngressMixin, _Request):
    __slots__ = ['_scope', '_receive', '_send']

    def __init__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
        max_content_length: Optional[int] = None,
        body_timeout: Optional[int] = None
    ):
        super().__init__(scope, receive, send)
        self.max_content_length = max_content_length
        self.body_timeout = body_timeout
        self._now = datetime.utcnow()
        self.method = scope['method']

    @cachedprop
    def _input(self):
        return Body(self._receive, self.max_content_length)

    @cachedprop
    async def body(self) -> bytes:
        if (
            self.max_content_length and
            self.content_length > self.max_content_length
        ):
            raise HTTP(413, 'Request entity too large')
        try:
            rv = await asyncio.wait_for(self._input, timeout=self.body_timeout)
        except asyncio.TimeoutError:
            raise HTTP(408, 'Request timeout')
        return rv

    async def push_promise(self, path: str):
        if "http.response.push" not in self._scope.get("extensions", {}):
            return
        await self._send({
            "type": "http.response.push",
            "path": path,
            "headers": [
                (key.encode("latin-1"), self.headers[key].encode("latin-1"))
                for key in _push_headers & set(self.headers.keys())
            ]
        })


class Websocket(ASGIIngressMixin, _Websocket):
    __slots__ = ['_scope', '_receive', '_send', '_accepted']

    def __init__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send
    ):
        super().__init__(scope, receive, send)
        self._accepted = False
        self._flow_receive = None
        self._flow_send = None
        self.receive = self._accept_and_receive
        self.send = self._accept_and_send

    @property
    def _asgi_spec_version(self) -> int:
        return int(''.join(
            self._scope.get('asgi', {}).get('spec_version', '2.0').split('.')
        ))

    def _encode_headers(
        self,
        headers: Dict[str, str]
    ) -> List[Tuple[bytes, bytes]]:
        return [
            (key.encode('utf-8'), val.encode('utf-8'))
            for key, val in headers.items()
        ]

    async def accept(
        self,
        headers: Optional[Dict[str, str]] = None,
        subprotocol: Optional[str] = None
    ):
        if self._accepted:
            return
        message: Dict[str, Any] = {
            'type': 'websocket.accept',
            'subprotocol': subprotocol
        }
        if headers and self._asgi_spec_version > 20:
            message['headers'] = self._encode_headers(headers)
        await self._send(message)
        self._accepted = True
        self.receive = self._wrapped_receive
        self.send = self._wrapped_send

    async def _wrapped_receive(self) -> Any:
        data = await self._receive()
        for method in self._flow_receive:  # type: ignore
            data = method(data)
        return data

    async def _wrapped_send(self, data: Any):
        for method in self._flow_send:  # type: ignore
            data = method(data)
        if isinstance(data, str):
            await self._send({'type': 'websocket.send', 'text': data})
        else:
            await self._send({'type': 'websocket.send', 'bytes': data})
