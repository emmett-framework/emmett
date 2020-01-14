# -*- coding: utf-8 -*-
"""
    emmett.asgi.workers
    -------------------

    Provides ASGI gunicorn workers.

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

from uvicorn.workers import UvicornWorker as _UvicornWorker


class EmmettWorker(_UvicornWorker):
    CONFIG_KWARGS = {
        "loop": "uvloop",
        "http": "httptools",
        "proxy_headers": False,
        "interface": "asgi3"
    }


class EmmettH11Worker(EmmettWorker):
    CONFIG_KWARGS = {
        "loop": "asyncio",
        "http": "h11",
        "proxy_headers": False,
        "interface": "asgi3"
    }
