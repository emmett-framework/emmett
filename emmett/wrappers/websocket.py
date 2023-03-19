# -*- coding: utf-8 -*-
"""
    emmett.wrappers.websocket
    -------------------------

    Provides http websocket wrappers.

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

from abc import abstractmethod
from typing import Any, Dict, Optional

from . import IngressWrapper


class Websocket(IngressWrapper):
    __slots__ = ['_flow_receive', '_flow_send', 'receive', 'send']

    def _bind_flow(self, flow_receive, flow_send):
        self._flow_receive = flow_receive
        self._flow_send = flow_send

    @abstractmethod
    async def accept(
        self,
        headers: Optional[Dict[str, str]] = None,
        subprotocol: Optional[str] = None
    ):
        ...

    async def _accept_and_receive(self) -> Any:
        await self.accept()
        return await self.receive()

    async def _accept_and_send(self, data: Any):
        await self.accept()
        await self.send(data)

    @abstractmethod
    async def _wrapped_receive(self) -> Any: ...

    @abstractmethod
    async def _wrapped_send(self, data: Any): ...
