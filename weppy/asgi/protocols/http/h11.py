# -*- coding: utf-8 -*-

from . import ProtocolWrapper, protocols


@protocols.register('h11', packages=['h11'])
class H11Protocol(ProtocolWrapper):
    @classmethod
    def protocol_cls(cls):
        from uvicorn.protocols.http.h11_impl import H11Protocol
        return H11Protocol
