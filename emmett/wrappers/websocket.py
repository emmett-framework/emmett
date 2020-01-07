# -*- coding: utf-8 -*-
"""
    emmett.wrappers.websocket
    -------------------------

    Provides http websocket wrappers.

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

from . import ScopeWrapper


class Websocket(ScopeWrapper):
    __slots__ = [
        '_wreceive', '_wsend', '_accepted', 'receive', 'send',
        '_flow_receive', '_flow_send'
    ]

    def __init__(self, scope, receive, send):
        super().__init__(scope)
        self._wreceive = receive
        self._wsend = send
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
        await self._wsend(message)
        self._accepted = True
        self.receive = self._receive
        self.send = self._send

    async def _accept_and_receive(self):
        await self.accept()
        return await self.receive()

    async def _accept_and_send(self, data):
        await self.accept()
        await self.send(data)

    async def _receive(self):
        data = await self._wreceive()
        for method in self._flow_receive:
            data = method(data)
        return data

    async def _send(self, data):
        for method in self._flow_send:
            data = method(data)
        if isinstance(data, str):
            await self._wsend({'type': 'websocket.send', 'text': data})
        else:
            await self._wsend({'type': 'websocket.send', 'bytes': data})
