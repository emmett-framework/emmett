# -*- coding: utf-8 -*-
"""
    weppy.http
    ----------

    Provides the HTTP interface for weppy.

    :copyright: (c) 2014-2017 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

from ._compat import text_type, to_bytes
from .globals import current


class HTTP(Exception):
    status_codes = {
        200: 'OK',
        201: 'CREATED',
        202: 'ACCEPTED',
        203: 'NON-AUTHORITATIVE INFORMATION',
        204: 'NO CONTENT',
        205: 'RESET CONTENT',
        206: 'PARTIAL CONTENT',
        301: 'MOVED PERMANENTLY',
        302: 'FOUND',
        303: 'SEE OTHER',
        304: 'NOT MODIFIED',
        305: 'USE PROXY',
        307: 'TEMPORARY REDIRECT',
        400: 'BAD REQUEST',
        401: 'UNAUTHORIZED',
        403: 'FORBIDDEN',
        404: 'NOT FOUND',
        405: 'METHOD NOT ALLOWED',
        406: 'NOT ACCEPTABLE',
        407: 'PROXY AUTHENTICATION REQUIRED',
        408: 'REQUEST TIMEOUT',
        409: 'CONFLICT',
        410: 'GONE',
        411: 'LENGTH REQUIRED',
        412: 'PRECONDITION FAILED',
        413: 'REQUEST ENTITY TOO LARGE',
        414: 'REQUEST-URI TOO LONG',
        415: 'UNSUPPORTED MEDIA TYPE',
        416: 'REQUESTED RANGE NOT SATISFIABLE',
        417: 'EXPECTATION FAILED',
        422: 'UNPROCESSABLE ENTITY',
        500: 'INTERNAL SERVER ERROR',
        501: 'NOT IMPLEMENTED',
        502: 'BAD GATEWAY',
        503: 'SERVICE UNAVAILABLE',
        504: 'GATEWAY TIMEOUT',
        505: 'HTTP VERSION NOT SUPPORTED',
    }

    def __init__(self, status_code, body=u'', headers=None, cookies=None):
        self.status_code = status_code
        self.status_name = HTTP.status_codes.get(status_code, status_code)
        self._set_body(body)
        self.headers = list(headers.items()) if headers else []
        if cookies:
            self.headers += HTTP.cookies2header(cookies)
        #if status_code != 200:
        #    if str(status_code)[0] == '4' and len(self.body) < 512:
        #        self.body += '<!-- %s //-->' % ('x' * 512)  # trick IE

    def _set_body(self, body):
        if body is None:
            self.body = []
        elif isinstance(body, (text_type, bytes, bytearray)):
            body = to_bytes(body)
            self.body = [body]
        else:
            self.body = body

    def to(self, environ, start_response):
        start_response(
            "%s %s" % (self.status_code, self.status_name), self.headers)
        if environ.get('REQUEST_METHOD', '') == 'HEAD':
            return [to_bytes('')]
        return self.body

    @staticmethod
    def cookies2header(cookies):
        headers = []
        for cookie in cookies.values():
            headers.append(('Set-Cookie', str(cookie)[11:]))
        return headers

    @staticmethod
    def redirect(location, status_code=303):
        current.response.status = status_code
        location = location.replace('\r', '%0D').replace('\n', '%0A')
        raise HTTP(status_code, headers=dict(Location=location))


redirect = HTTP.redirect
