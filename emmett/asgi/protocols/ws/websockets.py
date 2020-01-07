# -*- coding: utf-8 -*-
"""
    emmett.asgi.protocols.ws.websockets
    -----------------------------------

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

from . import ProtocolWrapper, protocols


@protocols.register('websockets', packages=['websockets'])
class WebsocketsProtocol(ProtocolWrapper):
    @classmethod
    def protocol_cls(cls):
        from uvicorn.protocols.websockets.websockets_impl import (
            WebSocketProtocol
        )
        return WebSocketProtocol
