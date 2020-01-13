# -*- coding: utf-8 -*-
"""
    emmett.asgi.protocols.ws.wsproto
    --------------------------------

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

from . import ProtocolWrapper, protocols


@protocols.register('wsproto', packages=['wsproto'])
class WSProtoProtocol(ProtocolWrapper):
    @classmethod
    def protocol_cls(cls):
        from uvicorn.protocols.websockets.wsproto_impl import WSProtocol
        return WSProtocol
