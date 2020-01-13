# -*- coding: utf-8 -*-
"""
    emmett.asgi.protocols.http.httptools
    ------------------------------------

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

from . import ProtocolWrapper, protocols


@protocols.register('httptools', packages=['httptools'])
class HttpToolsProtocol(ProtocolWrapper):
    @classmethod
    def protocol_cls(cls):
        from uvicorn.protocols.http.httptools_impl import HttpToolsProtocol
        return HttpToolsProtocol
