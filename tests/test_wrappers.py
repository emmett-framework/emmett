# -*- coding: utf-8 -*-
"""
    tests.wrappers
    --------------

    Test Emmett wrappers module
"""

from helpers import current_ctx
from emmett.asgi.wrappers import Request
from emmett.testing.env import ScopeBuilder
from emmett.wrappers.response import Response


def test_request():
    scope, _ = ScopeBuilder(
        path='/?foo=bar',
        method='GET',
    ).get_data()
    request = Request(scope, None, None)

    assert request.query_params == {'foo': 'bar'}
    assert request.client == '127.0.0.1'


def test_response():
    response = Response()

    assert response.status == 200
    assert response.headers['content-type'] == 'text/plain'


def test_req_ctx():
    with current_ctx('/?foo=bar') as ctx:
        assert isinstance(ctx.request, Request)
        assert isinstance(ctx.response, Response)
