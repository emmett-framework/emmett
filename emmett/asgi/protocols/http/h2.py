# -*- coding: utf-8 -*-
"""
    emmett.asgi.protocols.http.h2
    -----------------------------

    Provides HTTP h2 protocol implementation

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

from __future__ import annotations

import asyncio

from collections import defaultdict
from functools import partial
from typing import Any, List, Tuple
from urllib.parse import unquote

import h11
import h2.config
import h2.connection
import h2.events
import h2.exceptions

from uvicorn.protocols.utils import get_client_addr, get_path_with_query_string

from .helpers import (
    TRACE_LOG_LEVEL,
    ASGICycle,
    Config,
    HTTPProtocol,
    ServerState,
    _service_unavailable
)

HIGH_WATER_LIMIT = 65536


class EventsRegistry(defaultdict):
    def __init__(self):
        super().__init__(lambda: (lambda *args, **kwargs: None))

    def register(self, key: Any):
        def wrap(f):
            self[key] = f
            return f
        return wrap


class H2Protocol(HTTPProtocol):
    __slots__ = ["conn", "streams"]

    alpn_protocols = ["h2"]

    def __init__(self, config: Config, server_state: ServerState, _loop=None):
        super().__init__(config=config, server_state=server_state, _loop=_loop)
        self.conn = h2.connection.H2Connection(
            config=h2.config.H2Configuration(
                client_side=False,
                header_encoding=None
            )
        )
        self.streams = {}

    def connection_made(self, transport: asyncio.Transport, init: bool = False):
        super().connection_made(transport)
        if init:
            self.conn.initiate_connection()
            self.transport.write(self.conn.data_to_send())

    def connection_lost(self, exc):
        self.connections.discard(self)

        if self.logger.level <= TRACE_LOG_LEVEL:
            prefix = "%s:%d - " % tuple(self.addr_remote) if self.addr_remote else ""
            self.logger.log(TRACE_LOG_LEVEL, "%sConnection lost", prefix)

        for stream in self.streams.values():
            stream.message_event.set()
        if self.flow is not None:
            self.flow.resume_writing()

    def handle_upgrade_from_h11(
        self,
        transport: asyncio.Protocol,
        upgrade_event: h11.Request,
        headers: List[Tuple[bytes, bytes]]
    ):
        self.connection_made(transport, init=False)

        settings = ""
        headers = [
            (b":method", upgrade_event.method.encode("ascii")),
            (b":path", upgrade_event.target),
            (b":scheme", self.scheme.encode("ascii"))
        ]
        for name, value in headers:
            if name == b"http2-settings":
                settings = value.decode("latin-1")
            elif name == b"host":
                headers.append((b":authority", value))
            else:
                headers.append((name, value))

        self.conn.initiate_upgrade_connection(settings)
        self.transport.write(self.conn.data_to_send())
        event = h2.events.RequestReceived()
        event.stream_id = 1
        event.headers = headers
        on_request_received(self, event)

    def data_received(self, data: bytes):
        self._might_unset_keepalive()

        try:
            events = self.conn.receive_data(data)
        except h2.exceptions.ProtocolError:
            self.transport.write(self.conn.data_to_send())
            self.transport.close()
            return

        for event in events:
            eventsreg[type(event)](self, event)

    def shutdown(self):
        self.transport.write(self.conn.data_to_send())
        self.transport.close()

    def timeout_keep_alive_handler(self):
        if self.transport.is_closing():
            return

        self.conn.close_connection()
        self.transport.write(self.conn.data_to_send())
        self.transport.close()

    def on_response_complete(self, stream_id):
        self.server_state.total_requests += 1
        self.streams.pop(stream_id, None)
        if self.transport.is_closing():
            return

        if not self.streams:
            self._might_unset_keepalive()
            self.timeout_keep_alive_task = self.loop.call_later(
                self.timeout_keep_alive, self.timeout_keep_alive_handler
            )
        self.flow.resume_reading()


class H2ASGICycle(ASGICycle):
    __slots__ = ["scheme", "host", "stream_id", "new_request"]

    def __init__(
        self,
        scope,
        conn,
        protocol: H2Protocol,
        stream_id: int,
        host: bytes
    ):
        super().__init__(scope, conn, protocol)
        self.scheme = protocol.scheme.encode("ascii")
        self.host = host
        self.stream_id = stream_id
        self.new_request = partial(on_request_received, protocol)

    async def send(self, message):
        message_type = message["type"]

        if self.flow.write_paused and not self.disconnected:
            await self.flow.drain()

        if self.disconnected:
            return

        if message_type == "http.response.push":
            push_stream_id = self.conn.get_next_available_stream_id()
            headers = [
                (b":authority", self.host),
                (b":method", b"GET"),
                (b":path", message["path"].encode("ascii")),
                (b":scheme", self.scheme)
            ] + message["headers"]

            try:
                self.conn.push_stream(
                    stream_id=self.stream_id,
                    promised_stream_id=push_stream_id,
                    request_headers=headers
                )
                self.transport.write(self.conn.data_to_send())
            except h2.exceptions.ProtocolError:
                self.logger.debug("h2 protocol error.", exc_info=True)
            else:
                event = h2.events.RequestReceived()
                event.stream_id = push_stream_id
                event.headers = headers
                self.new_request(event)
        elif not self.response_started:
            # Sending response status line and headers
            if message_type != "http.response.start":
                msg = "Expected ASGI message 'http.response.start', but got '%s'."
                raise RuntimeError(msg % message_type)

            self.response_started = True

            status_code = message["status"]
            headers = (
                [(":status", str(status_code))] +
                self.default_headers +
                message.get("headers", [])
            )

            if self.access_log_enabled:
                self.access_logger.info(
                    '%s - "%s %s HTTP/%s" %d',
                    get_client_addr(self.scope),
                    self.scope["method"],
                    get_path_with_query_string(self.scope),
                    self.scope["http_version"],
                    status_code
                )

            self.conn.send_headers(self.stream_id, headers, end_stream=False)
            self.transport.write(self.conn.data_to_send())
        elif not self.response_completed:
            if message_type == "http.response.body":
                more_body = message.get("more_body", False)
                if self.scope["method"] == "HEAD":
                    body = b""
                else:
                    body = message.get("body", b"")
                self.conn.send_data(self.stream_id, body, end_stream=not more_body)
                self.transport.write(self.conn.data_to_send())
                if not more_body:
                    self.response_completed = True
                    self.message_event.set()
            else:
                msg = "Got unexpected ASGI message '%s'."
                raise RuntimeError(msg % message_type)

        if self.response_completed:
            self.on_response(self.stream_id)


eventsreg = EventsRegistry()


@eventsreg.register(h2.events.RequestReceived)
def on_request_received(protocol: H2Protocol, event: h2.events.RequestReceived):
    headers, pseudo_headers = [], {}
    for key, value in event.headers:
        if key[0] == b":"[0]:
            pseudo_headers[key] = value
        else:
            headers.append((key.lower(), value))
    host = pseudo_headers[b":authority"]
    headers.append((b"host", host))

    raw_path, _, query_string = pseudo_headers[b":path"].partition(b"?")
    scope = {
        "type": "http",
        "asgi": {
            "version": protocol.config.asgi_version,
            "spec_version": "2.1"
        },
        "http_version": "2",
        "server": protocol.addr_local,
        "client": protocol.addr_remote,
        "scheme": protocol.scheme,
        "method": pseudo_headers[b":method"].decode("ascii"),
        "root_path": protocol.root_path,
        "path": unquote(raw_path.decode("ascii")),
        "raw_path": raw_path,
        "query_string": query_string,
        "headers": headers,
        "extensions": {"http.response.push": {}}
    }

    if protocol.limit_concurrency is not None and (
        len(protocol.connections) >= protocol.limit_concurrency or
        len(protocol.tasks) >= protocol.limit_concurrency
    ):
        app = _service_unavailable
        message = "Exceeded concurrency limit."
        protocol.logger.warning(message)
    else:
        app = protocol.app

    protocol.streams[event.stream_id] = cycle = H2ASGICycle(
        scope=scope,
        conn=protocol.conn,
        protocol=protocol,
        stream_id=event.stream_id,
        host=host
    )
    task = protocol.loop.create_task(cycle.run_asgi(app))
    task.add_done_callback(protocol.tasks.discard)
    protocol.tasks.add(task)


@eventsreg.register(h2.events.DataReceived)
def on_data_received(protocol: H2Protocol, event: h2.events.DataReceived):
    try:
        stream = protocol.streams[event.stream_id]
    except KeyError:
        protocol.conn.reset_stream(
            event.stream_id,
            error_code=h2.errors.ErrorCodes.PROTOCOL_ERROR
        )
        return

    stream.body += event.data
    if len(stream.body) > HIGH_WATER_LIMIT:
        protocol.flow.pause_reading()
    stream.message_event.set()


@eventsreg.register(h2.events.StreamEnded)
def on_stream_ended(protocol: H2Protocol, event: h2.events.StreamEnded):
    try:
        stream = protocol.streams[event.stream_id]
    except KeyError:
        protocol.conn.reset_stream(
            event.stream_id,
            error_code=h2.errors.ErrorCodes.STREAM_CLOSED
        )
        return

    stream.transport.resume_reading()
    stream.more_body = False
    stream.message_event.set()


@eventsreg.register(h2.events.ConnectionTerminated)
def on_connection_terminated(
    protocol: H2Protocol,
    event: h2.events.ConnectionTerminated
):
    stream = protocol.streams.pop(event.last_stream_id, None)
    if stream:
        stream.disconnected = True
    protocol.conn.close_connection(last_stream_id=event.last_stream_id)
    protocol.transport.write(protocol.conn.data_to_send())
    protocol.transport.close()


@eventsreg.register(h2.events.StreamReset)
def on_stream_reset(protocol: H2Protocol, event: h2.events.StreamReset):
    protocol.streams.pop(event.stream_id, None)
