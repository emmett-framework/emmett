# -*- coding: utf-8 -*-

from contextlib import contextmanager

from weppy.asgi.handlers import RequestContext
from weppy.ctx import current
from weppy.testing.env import ScopeBuilder
from weppy.wrappers.request import Request
from weppy.wrappers.response import Response


class FakeRequestContext(RequestContext):
    def __init__(self, app, scope):
        self.request = Request(scope)
        self.response = Response()
        self.session = None


@contextmanager
def current_ctx(path):
    builder = ScopeBuilder(path)
    token = current._init_(FakeRequestContext, None, builder.get_data()[0])
    yield current
    current._close_(token)
