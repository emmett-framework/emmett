# -*- coding: utf-8 -*-
"""
    emmett.asgi.protocols.http.httptools
    ------------------------------------

    :copyright: (c) 2014-2019 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

from . import ProtocolWrapper, protocols


@protocols.register('httptools', packages=['httptools'])
class HttpToolsProtocol(ProtocolWrapper):
    @classmethod
    def protocol_cls(cls):
        from uvicorn.protocols.http.httptools_impl import HttpToolsProtocol
        return HttpToolsProtocol
