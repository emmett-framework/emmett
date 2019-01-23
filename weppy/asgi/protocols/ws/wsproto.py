# -*- coding: utf-8 -*-
"""
    weppy.asgi.protocols.ws.wsproto
    -------------------------------

    :copyright: (c) 2014-2019 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

from . import ProtocolWrapper, protocols


@protocols.register('wsproto', packages=['wsproto'])
class WSProtoProtocol(ProtocolWrapper):
    @classmethod
    def protocol_cls(cls):
        from uvicorn.protocols.ws.wsproto_impl import WSProtocol
        return WSProtocol
