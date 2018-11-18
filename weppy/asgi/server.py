# -*- coding: utf-8 -*-

import logging
import socket

from uvicorn.main import Server

from .loops import loops
from .protocols import protocols_http, protocols_ws


class NullLogger(logging.Logger):
    def handle(self, record):
        return


def run(
    app,
    host='127.0.0.1', port=8000, uds=None, fd=None,
    loop='auto', proto_http='auto', proto_ws='auto',
    # log_level='info', logger=None,
    access_log=True,
    debug=False,
    proxy_headers=False,
    root_path='',
    limit_concurrency=None, limit_max_requests=None, timeout_keep_alive=5
):
    if fd is None:
        sock = None
    else:
        host = None
        port = None
        sock = socket.fromfd(fd, socket.AF_UNIX, socket.SOCK_STREAM)

    loop = loops.get_loop(loop)
    protocol_cls_http = protocols_http.get_protocol(proto_http)
    protocol_cls_ws = protocols_ws.get_protocol(proto_ws)

    # if debug:
    #     app = DebugMiddleware(app)
    # if logger.level <= logging.DEBUG:
    #     app = MessageLoggerMiddleware(app)
    # if proxy_headers:
    #     app = ProxyHeadersMiddleware(app)

    connections = set()
    tasks = set()
    state = {"total_requests": 0}

    logger = NullLogger('null')

    def create_protocol():
        rv = protocol_cls_http(
            app=app,
            loop=loop,
            # logger=app.log,
            logger=logger,
            access_log=access_log,
            connections=connections,
            tasks=tasks,
            state=state,
            ws_protocol_class=protocol_cls_ws,
            root_path=root_path,
            limit_concurrency=limit_concurrency,
            timeout_keep_alive=timeout_keep_alive,
        )
        return rv

    server = Server(
        app=app,
        host=host,
        port=port,
        uds=uds,
        sock=sock,
        # logger=app.log,
        logger=logger,
        loop=loop,
        connections=connections,
        tasks=tasks,
        state=state,
        limit_max_requests=limit_max_requests,
        create_protocol=create_protocol,
        on_tick=protocol_cls_http.tick,
        install_signal_handlers=True,
        ready_event=None
    )
    server.run()
