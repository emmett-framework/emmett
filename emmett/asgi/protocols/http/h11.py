# -*- coding: utf-8 -*-
"""
    emmett.asgi.protocols.http.h11
    ------------------------------

    Provides HTTP h11 protocol implementation

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

import asyncio

import h11

from uvicorn.protocols.http.h11_impl import (
    HIGH_WATER_LIMIT,
    STATUS_PHRASES,
    H11Protocol as _H11Protocol,
    RequestResponseCycle,
    service_unavailable,
    unquote
)

from . import protocols
from .h2 import H2Protocol


@protocols.register("h11")
class H11Protocol(_H11Protocol):
    alpn_protocols = ["h2", "http/1.1"]
    h2_protocol_class = H2Protocol

    def handle_upgrade(self, event: h11.Request):
        upgrade_value = None
        for name, value in self.headers:
            if name == b"upgrade":
                upgrade_value = value.lower()
                break

        if upgrade_value == b"websocket" and self.ws_protocol_class:
            self.connections.discard(self)
            output = [event.method, b" ", event.target, b" HTTP/1.1\r\n"]
            for name, value in self.headers:
                output += [name, b": ", value, b"\r\n"]
            output.append(b"\r\n")
            protocol = self.ws_protocol_class(
                config=self.config,
                server_state=self.server_state
            )
            protocol.connection_made(self.transport)
            protocol.data_received(b"".join(output))
            self.transport.set_protocol(protocol)
        elif upgrade_value == b"h2c":
            self.connections.discard(self)
            self.transport.write(
                self.conn.send(
                    h11.InformationalResponse(
                        status_code=101,
                        headers=self.headers
                    )
                )
            )
            protocol = self.h2_protocol_class(
                config=self.config,
                server_state=self.server_state,
                _loop=self.loop
            )
            protocol.handle_upgrade_from_h11(self.transport, event, self.headers)
            self.transport.set_protocol(protocol)
        else:
            msg = "Unsupported upgrade request."
            self.logger.warning(msg)
            reason = STATUS_PHRASES[400]
            headers = [
                (b"content-type", b"text/plain; charset=utf-8"),
                (b"connection", b"close"),
            ]
            event = h11.Response(status_code=400, headers=headers, reason=reason)
            output = self.conn.send(event)
            self.transport.write(output)
            event = h11.Data(data=b"Unsupported upgrade request.")
            output = self.conn.send(event)
            self.transport.write(output)
            event = h11.EndOfMessage()
            output = self.conn.send(event)
            self.transport.write(output)
            self.transport.close()

    def handle_h2_assumed(self):
        self.connections.discard(self)
        protocol = self.h2_protocol_class(
            config=self.config,
            server_state=self.server_state,
            _loop=self.loop
        )
        protocol.connection_made(self.transport)
        protocol.data_received(
            b"PRI * HTTP/2.0\r\n\r\n" + self.conn.trailing_data[0]
        )
        self.transport.set_protocol(protocol)

    def handle_events(self):
        while True:
            try:
                event = self.conn.next_event()
            except h11.RemoteProtocolError as exc:
                msg = "Invalid HTTP request received."
                self.logger.warning(msg, exc_info=exc)
                self.transport.close()
                return
            event_type = type(event)

            if event_type is h11.NEED_DATA:
                break

            elif event_type is h11.PAUSED:
                # This case can occur in HTTP pipelining, so we need to
                # stop reading any more data, and ensure that at the end
                # of the active request/response cycle we handle any
                # events that have been buffered up.
                self.flow.pause_reading()
                break

            elif event_type is h11.Request:
                self.headers, upgrade_value = [], None
                for name, value in event.headers:
                    lname = name.lower()
                    self.headers.append((lname, value))
                    if lname == b"upgrade":
                        upgrade_value = value

                if upgrade_value:
                    self.handle_upgrade(event)
                    return
                elif (
                    event.method == b"PRI" and
                    event.target == b"*" and
                    event.http_version == b"2.0"
                ):
                    self.handle_h2_assumed()
                    return

                raw_path, _, query_string = event.target.partition(b"?")
                self.scope = {
                    "type": "http",
                    "asgi": {
                        "version": self.config.asgi_version,
                        "spec_version": "2.1",
                    },
                    "http_version": event.http_version.decode("ascii"),
                    "server": self.server,
                    "client": self.client,
                    "scheme": self.scheme,
                    "method": event.method.decode("ascii"),
                    "root_path": self.root_path,
                    "path": unquote(raw_path.decode("ascii")),
                    "raw_path": raw_path,
                    "query_string": query_string,
                    "headers": self.headers
                }

                # Handle 503 responses when 'limit_concurrency' is exceeded.
                if self.limit_concurrency is not None and (
                    len(self.connections) >= self.limit_concurrency
                    or len(self.tasks) >= self.limit_concurrency
                ):
                    app = service_unavailable
                    message = "Exceeded concurrency limit."
                    self.logger.warning(message)
                else:
                    app = self.app

                self.cycle = RequestResponseCycle(
                    scope=self.scope,
                    conn=self.conn,
                    transport=self.transport,
                    flow=self.flow,
                    logger=self.logger,
                    access_logger=self.access_logger,
                    access_log=self.access_log,
                    default_headers=self.default_headers,
                    message_event=asyncio.Event(),
                    on_response=self.on_response_complete,
                )
                task = self.loop.create_task(self.cycle.run_asgi(app))
                task.add_done_callback(self.tasks.discard)
                self.tasks.add(task)

            elif event_type is h11.Data:
                if self.conn.our_state is h11.DONE:
                    continue
                self.cycle.body += event.data
                if len(self.cycle.body) > HIGH_WATER_LIMIT:
                    self.flow.pause_reading()
                self.cycle.message_event.set()

            elif event_type is h11.EndOfMessage:
                if self.conn.our_state is h11.DONE:
                    self.transport.resume_reading()
                    self.conn.start_next_cycle()
                    continue
                self.cycle.more_body = False
                self.cycle.message_event.set()
