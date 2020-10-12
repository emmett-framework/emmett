# -*- coding: utf-8 -*-
"""
    emmett.asgi.protocols.http.httptools
    ------------------------------------

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

from uvicorn.protocols.http.httptools_impl import (
    HttpToolsProtocol as _HttpToolsProtocol
)

from . import protocols


@protocols.register("httptools")
class HTTPToolsProtocol(_HttpToolsProtocol):
    alpn_protocols = ["http/1.1"]
