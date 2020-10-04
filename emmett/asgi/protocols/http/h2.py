from __future__ import annotations

from collections import defaultdict, namedtuple
from functools import partial
from typing import Any
from urllib.parse import unquote

import h2.config
import h2.connection
import h2.events
import h2.exceptions

from uvicorn.protocols.utils import get_client_addr, get_path_with_query_string

from .helpers import ASGICycle, Config, HTTPProtocol, ServerState, _service_unavailable

HIGH_WATER_LIMIT = 65536
# Stream = namedtuple("Stream", ("scope", "cycle"))


class EventsRegistry(defaultdict):
    def __init__(self):
        super().__init__(lambda *args, **kwargs: None)

    def register(self, key: Any):
        def wrap(f):
            self[key] = f
            return f
        return wrap


class H2Protocol(HTTPProtocol):
    __slots__ = ["conn", "streams"]

    def __init__(self, config: Config, server_state: ServerState, _loop=None):
        super().__init__(config=config, server_state=server_state, _loop=_loop)
        self.conn = h2.connection.H2Connection(
            config=h2.config.H2Configuration(
                client_side=False,
                header_encoding=None
            )
        )
        self.streams = {}

    def data_received(self, data: bytes):
        super().data_received(data)
        self.conn.initiate_connection()
        try:
            events = self.conn.receive_data(data)
        except h2.exceptions.ProtocolError:
            self.transport.write(self.conn.data_to_send())
            self.transport.close()
            return

        for event in events:
            eventsreg[type(event)](self, event)
            # self.transport.write(self.conn.data_to_send())

    def shutdown(self):
        for stream_id in list(self.streams.keys()):
            stream = self.streams.pop(stream_id)
            if stream.cycle.response_complete:
                self.conn.close_connection(last_stream_id=stream_id)
                self.transport.write(self.conn.data_to_send())
            else:
                stream.cycle.keep_alive = False

    def timeout_keep_alive_handler(self):
        if not self.transport.is_closing():
            for stream_id in self.streams.keys():
                self.conn.close_connection(last_stream_id=stream_id)
                self.transport.write(self.conn.data_to_send())
            self.transport.close()


class H2ASGICycle(ASGICycle):
    __slots__ = ["stream_id", "new_request"]

    def __init__(
        self,
        stream_id,
        scope,
        conn,
        protocol: H2Protocol
    ):
        super().__init__(scope, conn, protocol)
        self.stream_id = stream_id
        self.new_request = partial(on_request_received, protocol)

    async def send(self, message):
        message_type = message["type"]

        if self.flow.write_paused and not self.disconnected:
            await self.flow.drain()

        if self.disconnected:
            return

        if not self.response_started:
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
                    status_code,
                    extra={"status_code": status_code, "scope": self.scope},
                )

            self.conn.send_headers(self.stream_id, headers, end_stream=True)
            self.transport.write(self.conn.data_to_send())

        elif not self.response_completed:
            # Sending response body
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
            elif message_type == "http.response.push":
                push_stream_id = self.conn.get_next_available_stream_id()
                headers = [
                    (b":method", b"GET"),
                    (b":path", message["path"])
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
            else:
                msg = "Got unexpected ASGI message '%s'."
                raise RuntimeError(msg % message_type)

        if self.response_completed:
            self.on_response()


eventsreg = EventsRegistry()


@eventsreg.register(h2.events.RequestReceived)
def on_request_received(protocol: H2Protocol, event: h2.events.RequestReceived):
    headers, pseudo_headers = [], {}
    for key, value in event.headers:
        if key[0] == b":":
            pseudo_headers[key] = value
        else:
            headers.append((key.lower(), value))

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
        "headers": headers
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

    cycle = H2ASGICycle(
        stream_id=event.stream_id,
        scope=scope,
        conn=protocol.conn,
        protocol=protocol
    )
    # protocol.streams[event.stream_id] = Stream(scope=scope, cycle=cycle)
    protocol.streams[event.stream_id] = cycle
    task = protocol.loop.create_task(cycle.run_asgi(app))
    task.add_done_callback(protocol.tasks.discard)
    protocol.tasks.add(task)


@eventsreg.register(h2.events.DataReceived)
def on_data_received(protocol: H2Protocol, event: h2.events.DataReceived):
    try:
        protocol.streams[event.stream_id].body += event.data
    except KeyError:
        protocol.conn.reset_stream(
            event.stream_id,
            error_code=h2.errors.ErrorCodes.PROTOCOL_ERROR
        )
        return

    if len(protocol.streams[event.stream_id].body) > HIGH_WATER_LIMIT:
        protocol.flow.pause_reading()
    protocol.message_event.set()


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
