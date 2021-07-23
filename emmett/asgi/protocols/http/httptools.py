# -*- coding: utf-8 -*-
"""
    emmett.asgi.protocols.http.httptools
    ------------------------------------

    Provides HTTP httptools protocol implementation

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

from uvicorn.protocols.http.httptools_impl import (
    HttpToolsProtocol as _HttpToolsProtocol,
    STATUS_LINE
)

from . import protocols


@protocols.register("httptools")
class HTTPToolsProtocol(_HttpToolsProtocol):
    alpn_protocols = ["http/1.1"]

    def handle_upgrade(self):
        upgrade_value = None
        for name, value in self.headers:
            if name == b"upgrade":
                upgrade_value = value.lower()

        if upgrade_value != b"websocket" or self.ws_protocol_class is None:
            msg = "Unsupported upgrade request."
            self.logger.warning(msg)

            content = [STATUS_LINE[400]]
            for name, value in self.default_headers:
                content.extend([name, b": ", value, b"\r\n"])
            content.extend(
                [
                    b"content-type: text/plain; charset=utf-8\r\n",
                    b"content-length: " + str(len(msg)).encode("ascii") + b"\r\n",
                    b"connection: close\r\n",
                    b"\r\n",
                    msg.encode("ascii"),
                ]
            )
            self.transport.write(b"".join(content))
            self.transport.close()
            return

        self.connections.discard(self)
        method = self.scope["method"].encode()
        output = [method, b" ", self.url, b" HTTP/1.1\r\n"]
        for name, value in self.scope["headers"]:
            output += [name, b": ", value, b"\r\n"]
        output.append(b"\r\n")
        protocol = self.ws_protocol_class(
            config=self.config,
            server_state=self.server_state,
            on_connection_lost=self.on_connection_lost,
        )
        protocol.connection_made(self.transport)
        protocol.data_received(b"".join(output))
        self.transport.set_protocol(protocol)
