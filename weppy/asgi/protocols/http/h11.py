# -*- coding: utf-8 -*-
"""
    weppy.asgi.protocols.http.h11
    -----------------------------

    :copyright: (c) 2014-2019 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

from . import ProtocolWrapper, protocols


@protocols.register('h11', packages=['h11'])
class H11Protocol(ProtocolWrapper):
    @classmethod
    def protocol_cls(cls):
        from uvicorn.protocols.http.h11_impl import H11Protocol
        return H11Protocol
