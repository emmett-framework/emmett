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
    loop_opt=False,
    log_level=None,
    log_access=False,
    workers=1,
    threads=1,
    threading_mode='workers',
    backlog=1024,
    backpressure=None,
    http='auto',
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
        loop_opt=loop_opt,
        http=http,
        websockets=enable_websockets,
        backlog=backlog,
        backpressure=backpressure,
        log_level=log_level,
        log_access=log_access,
        ssl_cert=ssl_certfile,
        ssl_key=ssl_keyfile
    )
    runner.serve()
