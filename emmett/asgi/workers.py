# -*- coding: utf-8 -*-
"""
    emmett.asgi.workers
    -------------------

    Provides ASGI gunicorn workers.

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

import asyncio
import logging
import signal

from gunicorn.workers.base import Worker as _Worker

from ..extensions import Signals
from .loops import loops
from .protocols import protocols_http, protocols_ws
from .server import Config, Server


class Worker(_Worker):
    EMMETT_CONFIG = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        logger = logging.getLogger("uvicorn.error")
        logger.handlers = self.log.error_log.handlers
        logger.setLevel(self.log.error_log.level)
        logger.propagate = False

        logger = logging.getLogger("uvicorn.access")
        logger.handlers = self.log.access_log.handlers
        logger.setLevel(self.log.access_log.level)
        logger.propagate = False

        config = {
            "app": None,
            "log_config": None,
            "timeout_keep_alive": self.cfg.keepalive,
            "timeout_notify": self.timeout,
            "callback_notify": self.callback_notify,
            "limit_max_requests": self.max_requests,
            "forwarded_allow_ips": self.cfg.forwarded_allow_ips
        }

        if self.cfg.is_ssl:
            config.update(
                ssl_keyfile=self.cfg.ssl_options.get("keyfile"),
                ssl_certfile=self.cfg.ssl_options.get("certfile"),
                ssl_version=self.cfg.ssl_options.get("ssl_version"),
                ssl_cert_reqs=self.cfg.ssl_options.get("cert_reqs"),
                ssl_ca_certs=self.cfg.ssl_options.get("ca_certs"),
                ssl_ciphers=self.cfg.ssl_options.get("ciphers")
            )

        if self.cfg.settings["backlog"].value:
            config["backlog"] = self.cfg.settings["backlog"].value

        config.update(self.EMMETT_CONFIG)
        config.update(
            http=protocols_http.get(config.get('http', 'auto')),
            ws=protocols_ws.get(config.get('ws', 'auto'))
        )

        self.config = Config(**config)

    def init_process(self):
        self.config.loop = loops.get(self.config.loop)
        super().init_process()

    def init_signals(self):
        for s in self.SIGNALS:
            signal.signal(s, signal.SIG_DFL)

    def run(self):
        self.config.app = self.wsgi
        self.config.app.send_signal(Signals.after_loop, loop=self.config.loop)
        server = Server(config=self.config)
        loop = asyncio.get_event_loop()
        loop.run_until_complete(server.serve(sockets=self.sockets))

    async def callback_notify(self):
        self.notify()


class EmmettWorker(Worker):
    EMMETT_CONFIG = {
        "loop": "uvloop",
        "http": "httptools",
        "proxy_headers": False,
        "interface": "asgi3"
    }


class EmmettH11Worker(EmmettWorker):
    EMMETT_CONFIG = {
        "loop": "asyncio",
        "http": "h11",
        "proxy_headers": False,
        "interface": "asgi3"
    }
