# -*- coding: utf-8 -*-

from . import ProtocolWrapper, protocols


@protocols.register('httptools', packages=['httptools'])
class HttpToolsProtocol(ProtocolWrapper):
    @classmethod
    def protocol_cls(cls):
        from uvicorn.protocols.http.httptools_impl import HttpToolsProtocol
        return HttpToolsProtocol
