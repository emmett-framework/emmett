# -*- coding: utf-8 -*-
"""
    emmett.rsgi.helpers
    -------------------

    Provides RSGI helpers

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

import asyncio

from granian.rsgi import WebsocketProtocol


class WSTransport:
    __slots__ = [
        'protocol', 'transport',
        'accepted', 'interrupted',
        'input', 'status', 'noop'
    ]

    def __init__(
        self,
        protocol: WebsocketProtocol
    ) -> None:
        self.protocol = protocol
        self.transport = None
        self.accepted = asyncio.Event()
        self.input = asyncio.Queue()
        self.interrupted = False
        self.status = 200
        self.noop = asyncio.Event()

    async def init(self):
        self.transport = await self.protocol.accept()
        self.accepted.set()

    @property
    def receive(self):
        return self.input.get
