# -*- coding: utf-8 -*-

from contextlib import contextmanager

from emmett.asgi.handlers import RequestContext
from emmett.ctx import current
from emmett.testing.env import ScopeBuilder
from emmett.wrappers.request import Request
from emmett.wrappers.response import Response


class FakeRequestContext(RequestContext):
    def __init__(self, app, scope):
        self.app = app
        self.request = Request(scope)
        self.response = Response()
        self.session = None


@contextmanager
def current_ctx(path, app=None):
    builder = ScopeBuilder(path)
    token = current._init_(FakeRequestContext, app, builder.get_data()[0])
    yield current
    current._close_(token)
