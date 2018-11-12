# -*- coding: utf-8 -*-
"""
    weppy.http
    ----------

    Provides the HTTP interface for weppy.

    :copyright: (c) 2014-2018 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

from ._compat import text_type, to_bytes
from .globals import current

status_codes = {
    100: '100 CONTINUE',
    101: '101 SWITCHING PROTOCOLS',
    200: '200 OK',
    201: '201 CREATED',
    202: '202 ACCEPTED',
    203: '203 NON-AUTHORITATIVE INFORMATION',
    204: '204 NO CONTENT',
    205: '205 RESET CONTENT',
    206: '206 PARTIAL CONTENT',
    207: '207 MULTI-STATUS',
    300: '300 MULTIPLE CHOICES',
    301: '301 MOVED PERMANENTLY',
    302: '302 FOUND',
    303: '303 SEE OTHER',
    304: '304 NOT MODIFIED',
    305: '305 USE PROXY',
    307: '307 TEMPORARY REDIRECT',
    400: '400 BAD REQUEST',
    401: '401 UNAUTHORIZED',
    403: '403 FORBIDDEN',
    404: '404 NOT FOUND',
    405: '405 METHOD NOT ALLOWED',
    406: '406 NOT ACCEPTABLE',
    407: '407 PROXY AUTHENTICATION REQUIRED',
    408: '408 REQUEST TIMEOUT',
    409: '409 CONFLICT',
    410: '410 GONE',
    411: '411 LENGTH REQUIRED',
    412: '412 PRECONDITION FAILED',
    413: '413 REQUEST ENTITY TOO LARGE',
    414: '414 REQUEST-URI TOO LONG',
    415: '415 UNSUPPORTED MEDIA TYPE',
    416: '416 REQUESTED RANGE NOT SATISFIABLE',
    417: '417 EXPECTATION FAILED',
    422: '422 UNPROCESSABLE ENTITY',
    500: '500 INTERNAL SERVER ERROR',
    501: '501 NOT IMPLEMENTED',
    502: '502 BAD GATEWAY',
    503: '503 SERVICE UNAVAILABLE',
    504: '504 GATEWAY TIMEOUT',
    505: '505 HTTP VERSION NOT SUPPORTED',
}


class HTTP(Exception):
    def __init__(self, status_code, body=u'', headers={}, cookies={}):
        self.status_code = status_code
        self.set_body(body or [])
        headers = headers or getattr(
            current, 'response', {'headers': {}})['headers']
        self.headers = list(headers.items())
        self.set_cookies(cookies)

    def set_body(self, body):
        if isinstance(body, (text_type, bytes, bytearray)):
            body = [to_bytes(body)]
        self.body = body

    def set_cookies(self, cookies):
        for cookie in cookies.values():
            self.headers.append(('Set-Cookie', str(cookie)[11:]))

    def to(self, environ, start_response):
        start_response(status_codes[self.status_code], self.headers)
        if environ['REQUEST_METHOD'] == 'HEAD':
            return [b'']
        return self.body

    @classmethod
    def redirect(cls, location, status_code=303):
        current.response.status = status_code
        location = location.replace('\r', '%0D').replace('\n', '%0A')
        raise cls(status_code, headers=dict(Location=location))


redirect = HTTP.redirect
