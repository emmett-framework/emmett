# -*- coding: utf-8 -*-
"""
    tests.http
    ----------------

    Test weppy http module

    :copyright: (c) 2014-2016 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

from datetime import datetime
from weppy.http import HTTP, redirect


def test_http_body_none():
    http = HTTP(200, body=None)

    assert http.body == []
    assert http.status_code == 200
    assert http.headers == []


def test_http_body_list():
    http = HTTP(200, body=[b'Test list'])

    assert http.body == [b'Test list']
    assert http.status_code == 200
    assert http.headers == []


def test_http():
    response = []
    buffer = []

    def start_response(status, headers):
        response[:] = [status, headers]
        return buffer.append

    http = HTTP(200, 'Hello World',
                headers={'X-Test': 'Hello Header'},
                cookies={'cookie_test': 'hello cookie'})

    assert http.body == [b'Hello World']
    assert http.status_code == 200
    assert http.headers == [('X-Test', 'Hello Header'), ('Set-Cookie', 'e')]

    assert http.to({'REQUEST_METHOD': 'HEAD'}, start_response) == [b'']
    assert http.to({'REQUEST_METHOD': 'GET'}, start_response) == [b'Hello World']


def test_redirect():
    from weppy.globals import current
    current.initialize({
        'PATH_INFO': '/',
        'REQUEST_METHOD': 'GET',
        'HTTP_HOST': 'localhost',
        'wsgi.url_scheme': 'http',
        'wpp.now': datetime.utcnow(),
        'wpp.application': 'test'
    })

    try:
        redirect('/redirect', 302)
    except HTTP as http_redirect:
        assert current.response.status == 302
        assert http_redirect.status_code == 302
        assert http_redirect.headers == [('Location', '/redirect')]
