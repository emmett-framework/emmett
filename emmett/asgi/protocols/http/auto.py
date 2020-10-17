# -*- coding: utf-8 -*-
"""
    emmett.asgi.protocols.http.auto
    -------------------------------

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

from . import protocols


if "httptools" in protocols:
    protocols.register("auto")(protocols.get("httptools"))
else:
    protocols.register("auto")(protocols.get("h11"))
