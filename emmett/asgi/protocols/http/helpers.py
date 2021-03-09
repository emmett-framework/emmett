# -*- coding: utf-8 -*-
"""
    emmett.asgi.protocols.helpers
    -----------------------------

    Provides HTTP protocols helpers

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

import asyncio
import logging

from uvicorn.main import ServerState
from uvicorn.protocols.utils import (
    get_local_addr,
    get_remote_addr,
    is_ssl
)

from ...helpers import Config

TRACE_LOG_LEVEL = 5


class FlowControl:
    __slots__ = [
        "_is_writable_event",
        "_transport",
        "read_paused",
        "write_paused"
    ]

    def __init__(self, transport: asyncio.Transport):
        self._transport = transport
        self.read_paused = False
        self.write_paused = False
        self._is_writable_event = asyncio.Event()
        self._is_writable_event.set()

    async def drain(self):
        await self._is_writable_event.wait()

    def pause_reading(self):
        if not self.read_paused:
            self.read_paused = True
            self._transport.pause_reading()

    def resume_reading(self):
        if self.read_paused:
            self.read_paused = False
            self._transport.resume_reading()

    def pause_writing(self):
        if not self.write_paused:
            self.write_paused = True
            self._is_writable_event.clear()

    def resume_writing(self):
        if self.write_paused:
            self.write_paused = False
            self._is_writable_event.set()


class HTTPProtocol(asyncio.Protocol):
    __slots__ = [
        "access_log_enabled",
        "access_logger",
        "addr_local",
        "addr_remote",
        "app",
        "config",
        "connections",
        "default_headers",
        "flow",
        "limit_concurrency",
        "logger",
        "loop",
        "root_path",
        "scheme",
        "server_state",
        "tasks",
        "timeout_keep_alive_task",
        "timeout_keep_alive",
        "transport",
        "ws_protocol_class"
    ]

    def __init__(self, config: Config, server_state: ServerState, _loop=None):
        self.config = config
        self.app = config.loaded_app
        self.loop = _loop or asyncio.get_event_loop()
        self.logger = logging.getLogger("uvicorn.error")
        self.access_logger = logging.getLogger("uvicorn.access")
        self.access_log_enabled = self.access_logger.hasHandlers()
        self.ws_protocol_class = config.ws_protocol_class
        self.root_path = config.root_path
        self.limit_concurrency = config.limit_concurrency

        # Timeouts
        self.timeout_keep_alive_task = None
        self.timeout_keep_alive = config.timeout_keep_alive

        # Shared server state
        self.server_state = server_state
        self.connections = server_state.connections
        self.tasks = server_state.tasks
        self.default_headers = server_state.default_headers

        # Per-connection state
        self.transport = None
        self.flow = None
        self.addr_local = None
        self.addr_remote = None
        self.scheme = None

    def connection_made(self, transport: asyncio.Transport):
        self.connections.add(self)

        self.transport = transport
        self.flow = FlowControl(transport)
        self.addr_local = get_local_addr(transport)
        self.addr_remote = get_remote_addr(transport)
        self.scheme = "https" if is_ssl(transport) else "http"

        if self.logger.level <= TRACE_LOG_LEVEL:
            prefix = "%s:%d - " % tuple(self.addr_remote) if self.addr_remote else ""
            self.logger.log(TRACE_LOG_LEVEL, "%sConnection made", prefix)

    def connection_lost(self, exc):
        self.connections.discard(self)

        if self.logger.level <= TRACE_LOG_LEVEL:
            prefix = "%s:%d - " % tuple(self.addr_remote) if self.addr_remote else ""
            self.logger.log(TRACE_LOG_LEVEL, "%sConnection lost", prefix)

        if self.flow is not None:
            self.flow.resume_writing()

    def eof_received(self):
        pass

    def _might_unset_keepalive(self):
        if self.timeout_keep_alive_task is not None:
            self.timeout_keep_alive_task.cancel()
            self.timeout_keep_alive_task = None

    def data_received(self, data: bytes):
        self._might_unset_keepalive()

    def on_response_complete(self):
        self.server_state.total_requests += 1
        if self.transport.is_closing():
            return

        self._might_unset_keepalive()
        self.timeout_keep_alive_task = self.loop.call_later(
            self.timeout_keep_alive, self.timeout_keep_alive_handler
        )
        self.flow.resume_reading()
        self.unblock_on_completed()

    def unblock_on_completed(self):
        pass

    def shutdown(self):
        pass

    def pause_writing(self):
        self.flow.pause_writing()

    def resume_writing(self):
        self.flow.resume_writing()

    def timeout_keep_alive_handler(self):
        pass


class ASGICycle:
    __slots__ = [
        "access_log_enabled",
        "access_logger",
        "body",
        "conn",
        "default_headers",
        "disconnected",
        "flow",
        "logger",
        "message_event",
        "more_body",
        "on_response",
        "response_completed",
        "response_started",
        "scope",
        "transport"
    ]

    def __init__(
        self,
        scope,
        conn,
        protocol: HTTPProtocol
    ):
        self.scope = scope
        self.conn = conn
        self.transport = protocol.transport
        self.flow = protocol.flow
        self.logger = protocol.logger
        self.access_logger = protocol.access_logger
        self.access_log_enabled = protocol.access_log_enabled
        self.default_headers = protocol.default_headers
        self.message_event = asyncio.Event()
        self.on_response = protocol.on_response_complete

        self.disconnected = False
        self.response_started = False
        self.response_completed = False

        self.body = b""
        self.more_body = True

    async def run_asgi(self, app):
        try:
            result = await app(self.scope, self.receive, self.send)
        except Exception as exc:
            msg = "Exception in ASGI application\n"
            self.logger.error(msg, exc_info=exc)
            if not self.response_started:
                await self.send_500_response()
            else:
                self.transport.close()
        else:
            if result is not None:
                msg = "ASGI callable should return None, but returned '%s'."
                self.logger.error(msg, result)
                self.transport.close()
            elif not self.response_started and not self.disconnected:
                msg = "ASGI callable returned without starting response."
                self.logger.error(msg)
                await self.send_500_response()
            elif not self.response_completed and not self.disconnected:
                msg = "ASGI callable returned without completing response."
                self.logger.error(msg)
                self.transport.close()
        finally:
            self.on_response = None

    async def receive(self):
        if not self.disconnected and not self.response_completed:
            self.flow.resume_reading()
            await self.message_event.wait()
            self.message_event.clear()

        if self.disconnected or self.response_completed:
            message = {"type": "http.disconnect"}
        else:
            message = {
                "type": "http.request",
                "body": self.body,
                "more_body": self.more_body,
            }
            self.body = b""

        return message

    async def send(self, message):
        raise NotImplementedError

    async def send_500_response(self):
        await self.send(
            {
                "type": "http.response.start",
                "status": 500,
                "headers": [
                    (b"content-type", b"text/plain; charset=utf-8"),
                    (b"connection", b"close")
                ]
            }
        )
        await self.send(
            {"type": "http.response.body", "body": b"Internal Server Error"}
        )


async def _service_unavailable(scope, receive, send):
    await send(
        {
            "type": "http.response.start",
            "status": 503,
            "headers": [
                (b"content-type", b"text/plain; charset=utf-8"),
                (b"connection", b"close")
            ]
        }
    )
    await send({"type": "http.response.body", "body": b"Service Unavailable"})
