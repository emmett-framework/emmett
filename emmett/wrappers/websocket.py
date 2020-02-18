# -*- coding: utf-8 -*-
"""
    emmett.wrappers.websocket
    -------------------------

    Provides http websocket wrappers.

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

from . import ScopeWrapper
from .typing import Scope, Receive, Send


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

    async def accept(self):
        if self._accepted:
            return
        message = {'type': 'websocket.accept', 'subprotocol': None}
        # TODO headers
        await self._send(message)
        self._accepted = True
        self.receive = self._wrapped_receive
        self.send = self._wrapped_send

    async def _accept_and_receive(self):
        await self.accept()
        return await self.receive()

    async def _accept_and_send(self, data):
        await self.accept()
        await self.send(data)

    async def _wrapped_receive(self):
        data = await self._receive()
        for method in self._flow_receive:
            data = method(data)
        return data

    async def _wrapped_send(self, data):
        for method in self._flow_send:
            data = method(data)
        if isinstance(data, str):
            await self._send({'type': 'websocket.send', 'text': data})
        else:
            await self._send({'type': 'websocket.send', 'bytes': data})
