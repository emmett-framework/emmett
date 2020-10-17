# -*- coding: utf-8 -*-
"""
    emmett.asgi.protocols.ws.auto
    -----------------------------

    Provides websocket auto protocol loader

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

from . import protocols


if "websockets" in protocols:
    protocols.register("auto")(protocols.get("websockets"))
else:
    protocols.register("auto")(protocols.get("wsproto"))
