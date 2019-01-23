# -*- coding: utf-8 -*-
"""
    tests.wrappers
    --------------

    Test weppy wrappers module

    :copyright: (c) 2014-2016 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""


from helpers import current_ctx
from weppy.testing.env import ScopeBuilder
from weppy.wrappers.request import Request
from weppy.wrappers.response import Response


def test_request():
    scope, _ = ScopeBuilder(
        path='/?foo=bar',
        method='GET',
    ).get_data()
    request = Request(scope)

    assert request.query_params == {'foo': 'bar'}
    assert request.client == '127.0.0.1'


def test_response():
    response = Response()

    assert response.status == 200
    assert response.headers == {'Content-Type': 'text/html; charset=utf-8'}


def test_req_ctx():
    with current_ctx('/?foo=bar') as ctx:
        assert isinstance(ctx.request, Request)
        assert isinstance(ctx.response, Response)
