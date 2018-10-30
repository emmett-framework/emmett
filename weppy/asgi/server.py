# -*- coding: utf-8 -*-


class Server(object):
    def __init__(
        self, app, host="127.0.0.1", port=8000, socket=None, loop="auto",
        http="auto", ws="auto"
    ):
        self.app = app
        self.host = host
        self.port = port
        self.socket = socket
        self.loop = loop
        self.protocol_http = http
        self.protocol_ws = ws
