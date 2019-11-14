# -*- coding: utf-8 -*-
"""
    weppy.wrappers.websocket
    ------------------------

    Provides http websocket wrappers.

    :copyright: (c) 2014-2019 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

from . import Wrapper
from .helpers import Headers


class Websocket(Wrapper):
    def __init__(self, scope, receive, send):
        self._scope = scope
        self._receive = receive
        self._send = send
        self._accepted = False
        # self.max_content_length = max_content_length
        # self.body_timeout = body_timeout
        self.scheme = scope['scheme']
        # self.method = scope['method']
        self.path = scope['emt.path']
        # self._input = scope['emt.input']
        self.headers = Headers(scope)
        self.host = self.headers.get('host')

    async def accept(self):
        if self._accepted:
            return
        message = {'type': 'websocket.accept', 'subprotocol': None}
        # TODO headers
        await self._send(message)
        self._accepted = True

    async def receive(self):
        await self.accept()
        return await self._scope['emt.wsqueue'].get()

    async def send(self, data):
        await self.accept()
        if isinstance(data, str):
            await self._send({'type': 'websocket.send', 'text': data})
        else:
            await self._send({'type': 'websocket.send', 'bytes': data})
