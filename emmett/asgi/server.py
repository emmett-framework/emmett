# -*- coding: utf-8 -*-
"""
    emmett.asgi.server
    ------------------

    Provides ASGI server wrapper over uvicorn

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

import logging
import multiprocessing
import os
import signal
import socket
import ssl
import sys
import threading

from abc import ABCMeta, abstractmethod
from typing import Any, Optional, Tuple

from uvicorn.config import logger as uvlogger
from uvicorn.server import Server

from .._internal import locate_app
from ..extensions import Signals
from ..logger import LOG_LEVELS
from .helpers import Config
from .loops import loops
from .protocols import protocols_http, protocols_ws

multiprocessing.allow_connection_pickling()


class Runner(metaclass=ABCMeta):
    def __init__(
        self,
        app_target: Tuple[str, Optional[str]],
        workers: int,
        **kwargs: Any
    ):
        self.app_target = app_target
        self.workers = workers
        self.cfgdata = {**kwargs}

    @staticmethod
    def serve(app_target, cfgdata, sockets=None):
        cfg = {**cfgdata}
        cfg["loop"] = loops.get(cfg.pop("loop"))
        cfg["http"] = protocols_http.get(cfg.pop("proto_http"))
        cfg["ws"] = protocols_ws.get(cfg.pop("proto_ws"))

        app = locate_app(*app_target)
        app.send_signal(Signals.after_loop, loop=cfg["loop"])

        cfg["access_log"] = (
            cfg["access_log"] is not None and cfg["access_log"] or
            bool(app.debug)
        )
        cfg["log_level"] = LOG_LEVELS[cfg["log_level"]] if cfg["log_level"] else (
            logging.DEBUG if app.debug else logging.WARNING
        )
        cfg["forwarded_allow_ips"] = cfg.pop("proxy_trust_ips")

        Server(Config(app=app, **cfg)).run(sockets=sockets)

    @abstractmethod
    def run(self):
        ...


class SingleRunner(Runner):
    def run(self):
        self.serve(self.app_target, self.cfgdata)


class MultiRunner(Runner):
    SIGNALS = {
        signal.SIGINT,
        signal.SIGTERM
    }

    def bind_socket(self):
        family = socket.AF_INET
        if self.cfgdata["host"] and ":" in self.cfgdata["host"]:
            family = socket.AF_INET6

        sock = socket.socket(family=family)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((self.cfgdata["host"], self.cfgdata["port"]))
        except OSError as exc:
            uvlogger.error(exc)
            sys.exit(1)
        sock.set_inheritable(True)
        return sock

    def signal_handler(self, *args, **kwargs):
        self.exit_event.set()

    @staticmethod
    def _subprocess_target(target, data, stdin_fileno):
        if stdin_fileno is not None:
            sys.stdin = os.fdopen(stdin_fileno)
        target(**data)

    def _subprocess_spawn(self, target, **data):
        try:
            stdin_fileno = sys.stdin.fileno()
        except OSError:
            stdin_fileno = None

        return multiprocessing.get_context("spawn").Process(
            target=self._subprocess_target,
            kwargs={
                "target": target,
                "data": data,
                "stdin_fileno": stdin_fileno
            }
        )

    def startup(self):
        for sig in self.SIGNALS:
            signal.signal(sig, self.signal_handler)

        for _ in range(self.workers):
            proc = self._subprocess_spawn(
                target=self.serve,
                cfgdata=self.cfgdata,
                app_target=self.app_target,
                sockets=self.sockets
            )
            proc.start()
            self.processes.append(proc)

    def shutdown(self):
        for proc in self.processes:
            proc.join()

    def run(self):
        self.processes = []
        self.sockets = [self.bind_socket()]
        self.exit_event = threading.Event()

        self.startup()
        self.exit_event.wait()
        self.shutdown()


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
    workers=1,
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
    if proxy_trust_ips is None:
        proxy_trust_ips = os.environ.get("PROXY_TRUST_IPS", "*")

    runner_cls = MultiRunner if workers > 1 else SingleRunner

    runner = runner_cls(
        app,
        workers,
        host=host,
        port=port,
        uds=uds,
        fd=fd,
        loop=loop,
        proto_http=proto_http,
        proto_ws=proto_ws,
        log_level=log_level,
        access_log=access_log,
        proxy_headers=proxy_headers,
        proxy_trust_ips=proxy_trust_ips,
        limit_concurrency=limit_concurrency,
        # limit_max_requests=None,
        backlog=backlog,
        timeout_keep_alive=timeout_keep_alive,
        # timeout_notify=30,
        ssl_certfile=ssl_certfile,
        ssl_keyfile=ssl_keyfile,
        ssl_cert_reqs=ssl_cert_reqs,
        ssl_ca_certs=ssl_ca_certs
    )
    runner.run()
