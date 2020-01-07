# -*- coding: utf-8 -*-
"""
    emmett.asgi.protocols.http.h11
    ------------------------------

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

from . import ProtocolWrapper, protocols


@protocols.register('h11', packages=['h11'])
class H11Protocol(ProtocolWrapper):
    @classmethod
    def protocol_cls(cls):
        from uvicorn.protocols.http.h11_impl import H11Protocol
        return H11Protocol
