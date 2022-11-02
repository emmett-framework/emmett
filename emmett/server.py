# -*- coding: utf-8 -*-
"""
    emmett.server
    -------------

    Provides server wrapper over granian

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

from typing import Optional

from granian import Granian


def run(
    interface,
    app,
    host='127.0.0.1',
    port=8000,
    loop='auto',
    log_level=None,
    workers=1,
    threads=None,
    threading_mode='runtime',
    backlog=2048,
    enable_websockets=True,
    ssl_certfile: Optional[str] = None,
    ssl_keyfile: Optional[str] = None
):
    app_path = ":".join([app[0], app[1] or "app"])
    runner = Granian(
        app_path,
        address=host,
        port=port,
        interface=interface,
        workers=workers,
        threads=threads,
        threading_mode=threading_mode,
        loop=loop,
        websockets=enable_websockets,
        backlog=backlog,
        log_level=log_level,
        ssl_cert=ssl_certfile,
        ssl_key=ssl_keyfile
    )
    runner.serve()
