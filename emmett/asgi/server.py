# -*- coding: utf-8 -*-
"""
    emmett.asgi.server
    ------------------

    Provides ASGI server wrapper over uvicorn

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

import logging
import os
import ssl

from typing import Optional

from uvicorn.main import Server

from ..extensions import Signals
from ..logger import LOG_LEVELS
from .helpers import Config
from .loops import loops
from .protocols import protocols_http, protocols_ws


def run(
    app,
    host='127.0.0.1',
    port=8000,
    uds=None,
    fd=None,
    loop='auto',
    proto_http='auto',
    proto_ws='auto',
    log_level=None,
    access_log=None,
    proxy_headers=False,
    proxy_trust_ips=None,
    limit_concurrency=None,
    # limit_max_requests=None,
    backlog=2048,
    timeout_keep_alive=0,
    # timeout_notify=30,
    ssl_certfile: Optional[str] = None,
    ssl_keyfile: Optional[str] = None,
    ssl_cert_reqs: int = ssl.CERT_NONE,
    ssl_ca_certs: Optional[str] = None
):
    loop = loops.get(loop)
    protocol_cls_http = protocols_http.get(proto_http)
    protocol_cls_ws = protocols_ws.get(proto_ws)

    app.send_signal(Signals.after_loop, loop=loop)

    if access_log is None:
        access_log = bool(app.debug)

    log_level = (
        LOG_LEVELS[log_level] if log_level else (
            logging.DEBUG if app.debug else logging.WARNING))

    if proxy_trust_ips is None:
        proxy_trust_ips = os.environ.get("PROXY_TRUST_IPS", "*")

    uvicorn_config = Config(
        app=app,
        host=host,
        port=port,
        uds=uds,
        fd=fd,
        loop=loop,
        http=protocol_cls_http,
        ws=protocol_cls_ws,
        log_level=log_level,
        access_log=access_log,
        debug=bool(app.debug),
        proxy_headers=proxy_headers,
        forwarded_allow_ips=proxy_trust_ips,
        limit_concurrency=limit_concurrency,
        # limit_max_requests=limit_max_requests,
        backlog=backlog,
        timeout_keep_alive=timeout_keep_alive,
        # timeout_notify=timeout_notify,
        ssl_certfile=ssl_certfile,
        ssl_keyfile=ssl_keyfile,
        ssl_cert_reqs=ssl_cert_reqs,
        ssl_ca_certs=ssl_ca_certs
    )
    server = Server(uvicorn_config)
    server.run()
