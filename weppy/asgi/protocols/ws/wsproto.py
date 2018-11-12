# -*- coding: utf-8 -*-

from . import ProtocolWrapper, protocols


@protocols.register('wsproto', packages=['wsproto'])
class WSProtoProtocol(ProtocolWrapper):
    @classmethod
    def protocol_cls(cls):
        from uvicorn.protocols.ws.wsproto_impl import WSProtocol
        return WSProtocol
