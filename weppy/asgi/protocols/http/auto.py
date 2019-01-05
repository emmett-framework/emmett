# -*- coding: utf-8 -*-

from . import ProtocolWrapper, protocols


@protocols.register('auto')
class AutoProtocol(ProtocolWrapper):
    @classmethod
    def protocol_cls(cls):
        if 'httptools' in protocols.builders:
            return protocols.get_protocol('httptools').builder.protocol_cls()
        return protocols.get_protocol('h11').builder.protocol_cls()
