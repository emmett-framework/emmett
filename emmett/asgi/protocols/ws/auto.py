# -*- coding: utf-8 -*-
"""
    emmett.asgi.protocols.ws.auto
    -----------------------------

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

from . import ProtocolWrapper, protocols


@protocols.register('auto')
class AutoProtocol(ProtocolWrapper):
    @classmethod
    def protocol_cls(cls):
        if 'websockets' in protocols.builders:
            return protocols.get_protocol('websockets').builder.protocol_cls()
        return protocols.get_protocol('wsproto').builder.protocol_cls()
