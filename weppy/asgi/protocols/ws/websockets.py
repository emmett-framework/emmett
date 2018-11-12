# -*- coding: utf-8 -*-

from . import ProtocolWrapper, protocols


@protocols.register('websockets', packages=['websockets'])
class WebsocketsProtocol(ProtocolWrapper):
    @classmethod
    def protocol_cls(cls):
        from uvicorn.protocols.ws.websockets_impl import WebSocketProtocol
        return WebSocketProtocol
