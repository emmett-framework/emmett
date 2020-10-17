# -*- coding: utf-8 -*-
"""
    tests.http
    ----------

    Test Emmett http module
"""

from helpers import current_ctx
from emmett.http import HTTP, HTTPBytes, HTTPResponse, redirect


def test_http_default():
    http = HTTP(200)

    assert http.encoded_body is b''
    assert http.status_code == 200
    assert http.headers == [(b'content-type', b'text/plain')]


def test_http_bytes():
    http = HTTPBytes(200)

    assert http.body == b''
    assert http.status_code == 200
    assert http.headers == [(b'content-type', b'text/plain')]


def test_http():
    response = []
    buffer = []

    def start_response(status, headers):
        response[:] = [status, headers]
        return buffer.append

    http = HTTP(
        200,
        'Hello World',
        headers={'x-test': 'Hello Header'},
        cookies={'cookie_test': 'Set-Cookie: hello cookie'}
    )

    assert http.encoded_body == b'Hello World'
    assert http.status_code == 200
    assert http.headers == [
        (b'x-test', b'Hello Header'), (b'set-cookie', b'hello cookie')
    ]


def test_redirect():
    with current_ctx('/') as ctx:
        try:
            redirect('/redirect', 302)
        except HTTPResponse as http_redirect:
            assert ctx.response.status == 302
            assert http_redirect.status_code == 302
            assert http_redirect.headers == [(b'location', b'/redirect')]
