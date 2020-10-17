# -*- coding: utf-8 -*-
"""
    emmett.asgi.protocols.ws.websockets
    -----------------------------------

    Provides websocket websockets protocol implementation

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

from uvicorn.protocols.websockets.websockets_impl import WebSocketProtocol

from . import protocols


protocols.register("websockets")(WebSocketProtocol)
