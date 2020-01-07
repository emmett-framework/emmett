# -*- coding: utf-8 -*-
"""
    emmett.asgi.protocols.http.auto
    -------------------------------

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

from . import ProtocolWrapper, protocols


@protocols.register('auto')
class AutoProtocol(ProtocolWrapper):
    @classmethod
    def protocol_cls(cls):
        if 'httptools' in protocols.builders:
            return protocols.get_protocol('httptools').builder.protocol_cls()
        return protocols.get_protocol('h11').builder.protocol_cls()
