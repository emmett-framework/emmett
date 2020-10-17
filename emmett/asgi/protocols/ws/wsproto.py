# -*- coding: utf-8 -*-
"""
    emmett.asgi.protocols.ws.wsproto
    --------------------------------

    Provides websocket wsproto protocol implementation

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

from uvicorn.protocols.websockets.wsproto_impl import WSProtocol

from . import protocols


protocols.register("wsproto")(WSProtocol)
