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
import sys

from gunicorn.arbiter import Arbiter
from gunicorn.workers.base import Worker as _Worker
from uvicorn.config import Config
from uvicorn.server import Server


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
                ssl_keyfile_password=self.cfg.ssl_options.get("password"),
                ssl_version=self.cfg.ssl_options.get("ssl_version"),
                ssl_cert_reqs=self.cfg.ssl_options.get("cert_reqs"),
                ssl_ca_certs=self.cfg.ssl_options.get("ca_certs"),
                ssl_ciphers=self.cfg.ssl_options.get("ciphers")
            )

        if self.cfg.settings["backlog"].value:
            config["backlog"] = self.cfg.settings["backlog"].value

        config.update(self.EMMETT_CONFIG)

        self.config = Config(**config)

    def init_process(self):
        self.config.setup_event_loop()
        super().init_process()

    def init_signals(self) -> None:
        for s in self.SIGNALS:
            signal.signal(s, signal.SIG_DFL)
        signal.signal(signal.SIGUSR1, self.handle_usr1)
        signal.siginterrupt(signal.SIGUSR1, False)

    async def _serve(self) -> None:
        self.config.app = self.wsgi
        server = Server(config=self.config)
        await server.serve(sockets=self.sockets)
        if not server.started:
            sys.exit(Arbiter.WORKER_BOOT_ERROR)

    def run(self) -> None:
        return asyncio.run(self._serve())

    async def callback_notify(self) -> None:
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
        "loop": "auto",
        "http": "h11",
        "proxy_headers": False,
        "interface": "asgi3"
    }
