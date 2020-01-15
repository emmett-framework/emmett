# -*- coding: utf-8 -*-
"""
    emmett.asgi.server
    ------------------

    Provides ASGI server wrapper over uvicorn.

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

import logging

from uvicorn.config import Config as UvicornConfig, create_ssl_context
from uvicorn.lifespan.on import LifespanOn
from uvicorn.main import Server
from uvicorn.middleware.debug import DebugMiddleware

from ..logger import LOG_LEVELS
from .loops import loops
from .protocols import protocols_http, protocols_ws


class Config(UvicornConfig):
    def setup_event_loop(self):
        pass

    def load(self):
        assert not self.loaded

        if self.is_ssl:
            self.ssl = create_ssl_context(
                keyfile=self.ssl_keyfile,
                certfile=self.ssl_certfile,
                ssl_version=self.ssl_version,
                cert_reqs=self.ssl_cert_reqs,
                ca_certs=self.ssl_ca_certs,
                ciphers=self.ssl_ciphers,
            )
        else:
            self.ssl = None

        encoded_headers = [
            (key.lower().encode("latin1"), value.encode("latin1"))
            for key, value in self.headers
        ]
        self.encoded_headers = (
            encoded_headers if b"server" in dict(encoded_headers) else
            [(b"server", b"Emmett")] + encoded_headers
        )

        self.http_protocol_class = self.http
        self.ws_protocol_class = self.ws
        self.lifespan_class = LifespanOn

        self.loaded_app = self.app
        self.interface = "asgi3"

        if self.debug:
            self.loaded_app = DebugMiddleware(self.loaded_app)

        self.loaded = True


def run(
    app,
    host='127.0.0.1', port=8000, uds=None, fd=None,
    loop='auto', proto_http='auto', proto_ws='auto',
    log_level=None, access_log=None,
    proxy_headers=False,
    limit_concurrency=None,
    # limit_max_requests=None,
    timeout_keep_alive=0
    # timeout_notify=30
):
    loop = loops.get_loop(loop)
    protocol_cls_http = protocols_http.get_protocol(proto_http)
    protocol_cls_ws = protocols_ws.get_protocol(proto_ws)

    app.send_signal('after_loop', loop=loop)

    if access_log is None:
        access_log = bool(app.debug)

    log_level = (
        LOG_LEVELS[log_level] if log_level else (
            logging.DEBUG if app.debug else logging.WARNING))

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
        limit_concurrency=limit_concurrency,
        # limit_max_requests=limit_max_requests,
        timeout_keep_alive=timeout_keep_alive,
        # timeout_notify=timeout_notify
    )
    server = Server(uvicorn_config)
    server.run()
