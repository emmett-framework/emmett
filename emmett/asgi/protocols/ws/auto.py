# -*- coding: utf-8 -*-
"""
    emmett.asgi.protocols.ws.auto
    -----------------------------

    :copyright: (c) 2014-2019 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

from . import ProtocolWrapper, protocols


@protocols.register('auto')
class AutoProtocol(ProtocolWrapper):
    @classmethod
    def protocol_cls(cls):
        if 'websockets' in protocols.builders:
            return protocols.get_protocol('websockets').builder.protocol_cls()
        return protocols.get_protocol('wsproto').builder.protocol_cls()
