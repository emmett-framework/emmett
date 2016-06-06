# -*- coding: utf-8 -*-
"""
    tests.globals
    ----------------

    Test weppy globals module

    :copyright: (c) 2014-2016 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""


from weppy.globals import Request, Response, Current
from weppy.testing.env import EnvironBuilder


def test_request():
    builder = EnvironBuilder(
        path='/?foo=bar',
        method='GET',
    )
    request = Request(builder.get_environ())

    assert request.params == {'foo': 'bar'}
    assert request.client == '127.0.0.1'


def test_response():
    builder = EnvironBuilder(
        path='/?foo=bar',
        method='GET',
    )
    response = Response(builder.get_environ())

    assert response.status == 200
    assert response.headers == {'Content-Type': 'text/html; charset=utf-8'}


def test_current():
    builder = EnvironBuilder(
        path='/?foo=bar',
        method='GET',
    )
    current = Current()
    environ = builder.get_environ()
    current.initialize(environ)

    assert current.environ == environ
    assert isinstance(current.request, Request)
    assert isinstance(current.response, Response)
