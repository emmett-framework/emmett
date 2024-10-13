# -*- coding: utf-8 -*-
"""
tests.helpers
-------------

Tests helpers
"""

from contextlib import contextmanager

from emmett_core.protocols.rsgi.test_client.scope import ScopeBuilder

from emmett.ctx import RequestContext, WSContext, current
from emmett.datastructures import sdict
from emmett.rsgi.wrappers import Request, Websocket
from emmett.serializers import Serializers
from emmett.wrappers.response import Response


json_dump = Serializers.get_for("json")


class FakeRequestContext(RequestContext):
    def __init__(self, app, scope):
        self.app = app
        self.request = Request(scope, scope.path, None, None)
        self.response = Response()
        self.session = None


class FakeWSTransport:
    def __init__(self):
        self._send_storage = []

    async def receive(self):
        return json_dump({"foo": "bar"})

    async def send_str(self, data):
        self._send_storage.append(data)

    async def send_bytes(self, data):
        self._send_storage.append(data)


class FakeWsProto:
    def __init__(self):
        self.transport = None

    async def init(self):
        self.transport = FakeWSTransport()

    async def receive(self):
        return sdict(data=await self.transport.receive())

    def close(self):
        pass


class FakeWSContext(WSContext):
    def __init__(self, app, scope):
        self.app = app
        self._proto = FakeWsProto()
        self.websocket = Websocket(scope, scope.path, self._proto)
        self._receive_storage = []

    @property
    def _send_storage(self):
        return self._proto.transport._send_storage


@contextmanager
def current_ctx(path, app=None):
    builder = ScopeBuilder(path)
    token = current._init_(FakeRequestContext(app, builder.get_data()[0]))
    yield current
    current._close_(token)


@contextmanager
def ws_ctx(path, app=None):
    builder = ScopeBuilder(path)
    scope_data = builder.get_data()[0]
    scope_data.proto = "ws"
    token = current._init_(FakeWSContext(app, scope_data))
    yield current
    current._close_(token)
