# -*- coding: utf-8 -*-
"""
    emmett.wrappers.websocket
    -------------------------

    Provides http websocket wrappers.

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

from typing import Any, Dict, List, Optional, Tuple

from ..asgi.typing import Scope, Receive, Send
from . import ScopeWrapper


class Websocket(ScopeWrapper):
    __slots__ = ('_accepted', 'receive', 'send', '_flow_receive', '_flow_send')

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

    def _bind_flow(self, flow_receive, flow_send):
        self._flow_receive = flow_receive
        self._flow_send = flow_send

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

    async def _accept_and_receive(self) -> Any:
        await self.accept()
        return await self.receive()

    async def _accept_and_send(self, data: Any):
        await self.accept()
        await self.send(data)

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
