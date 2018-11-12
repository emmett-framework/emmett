# -*- coding: utf-8 -*-

from . import ProtocolWrapper, protocols


@protocols.register('auto')
class AutoProtocol(ProtocolWrapper):
    @classmethod
    def protocol_cls(cls):
        if 'websockets' in protocols.builders:
            return protocols.get_protocol('websockets').builder.protocol_cls()
        return protocols.get_protocol('wsproto').builder.protocol_cls()
