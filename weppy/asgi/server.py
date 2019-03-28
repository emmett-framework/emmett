# -*- coding: utf-8 -*-
"""
    weppy.asgi.server
    -----------------

    Provides ASGI server wrapper over uvicorn.

    :copyright: (c) 2014-2019 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

import logging

from uvicorn.config import Config as UvicornConfig
from uvicorn.lifespan.on import LifespanOn
from uvicorn.main import Server

from ..logger import LOG_LEVELS
from .loops import loops
from .protocols import protocols_http, protocols_ws


class Config(UvicornConfig):
    def setup_event_loop(self):
        pass

    def load(self):
        assert not self.loaded

        encoded_headers = [
            (key.lower().encode("latin1"), value.encode("latin1"))
            for key, value in self.headers
        ]
        self.encoded_headers = (
            encoded_headers if b"server" in dict(encoded_headers) else
            [(b"server", b"weppy")] + encoded_headers
        )

        self.http_protocol_class = self.http
        self.ws_protocol_class = self.ws
        self.lifespan_class = LifespanOn

        self.loaded_app = self.app
        self.interface = "asgi3"

        self.loaded = True


def _build_server_logger(app, level=None):
    level = (
        LOG_LEVELS[level] if level else (
            logging.DEBUG if app.debug else logging.WARNING))
    log_format = '[SERVER] %(levelname)s %(message)s'
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(log_format))
    logger = logging.getLogger("uvicorn")
    logger.setLevel(level)
    logger.addHandler(handler)
    return logger


def run(
    app,
    host='127.0.0.1', port=8000, uds=None, fd=None,
    loop='auto', proto_http='auto', proto_ws='auto',
    log_level=None, access_log=None,
    # proxy_headers=False,
    limit_concurrency=None,
    # limit_max_requests=None,
    timeout_keep_alive=5, timeout_notify=30
):
    loop = loops.get_loop(loop)
    protocol_cls_http = protocols_http.get_protocol(proto_http)
    protocol_cls_ws = protocols_ws.get_protocol(proto_ws)

    if access_log is None:
        access_log = bool(app.debug)

    uvicorn_config = Config(
        app=app,
        host=host,
        port=port,
        uds=uds,
        fd=fd,
        loop=loop,
        http=protocol_cls_http,
        ws=protocol_cls_ws,
        logger=_build_server_logger(app, log_level),
        access_log=access_log,
        debug=bool(app.debug),
        limit_concurrency=limit_concurrency,
        # limit_max_requests=limit_max_requests,
        timeout_keep_alive=timeout_keep_alive,
        timeout_notify=timeout_notify
    )
    server = Server(uvicorn_config)
    server.run()
