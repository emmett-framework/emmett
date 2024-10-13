# -*- coding: utf-8 -*-
"""
emmett.http
-----------

Provides the HTTP interfaces.

:copyright: 2014 Giovanni Barillari
:license: BSD-3-Clause
"""

from __future__ import annotations

from emmett_core.http.helpers import redirect as _redirect
from emmett_core.http.response import (
    HTTPAsyncIterResponse as HTTPAsyncIter,
    HTTPBytesResponse as HTTPBytes,
    HTTPFileResponse as HTTPFile,
    HTTPIOResponse as HTTPIO,
    HTTPIterResponse as HTTPIter,
    HTTPResponse as HTTPResponse,
    HTTPStringResponse as HTTPStringResponse,
)

from .ctx import current


HTTP = HTTPStringResponse

status_codes = {
    100: "100 CONTINUE",
    101: "101 SWITCHING PROTOCOLS",
    200: "200 OK",
    201: "201 CREATED",
    202: "202 ACCEPTED",
    203: "203 NON-AUTHORITATIVE INFORMATION",
    204: "204 NO CONTENT",
    205: "205 RESET CONTENT",
    206: "206 PARTIAL CONTENT",
    207: "207 MULTI-STATUS",
    300: "300 MULTIPLE CHOICES",
    301: "301 MOVED PERMANENTLY",
    302: "302 FOUND",
    303: "303 SEE OTHER",
    304: "304 NOT MODIFIED",
    305: "305 USE PROXY",
    307: "307 TEMPORARY REDIRECT",
    400: "400 BAD REQUEST",
    401: "401 UNAUTHORIZED",
    403: "403 FORBIDDEN",
    404: "404 NOT FOUND",
    405: "405 METHOD NOT ALLOWED",
    406: "406 NOT ACCEPTABLE",
    407: "407 PROXY AUTHENTICATION REQUIRED",
    408: "408 REQUEST TIMEOUT",
    409: "409 CONFLICT",
    410: "410 GONE",
    411: "411 LENGTH REQUIRED",
    412: "412 PRECONDITION FAILED",
    413: "413 REQUEST ENTITY TOO LARGE",
    414: "414 REQUEST-URI TOO LONG",
    415: "415 UNSUPPORTED MEDIA TYPE",
    416: "416 REQUESTED RANGE NOT SATISFIABLE",
    417: "417 EXPECTATION FAILED",
    422: "422 UNPROCESSABLE ENTITY",
    500: "500 INTERNAL SERVER ERROR",
    501: "501 NOT IMPLEMENTED",
    502: "502 BAD GATEWAY",
    503: "503 SERVICE UNAVAILABLE",
    504: "504 GATEWAY TIMEOUT",
    505: "505 HTTP VERSION NOT SUPPORTED",
}


def redirect(location: str, status_code: int = 303):
    _redirect(current, location, status_code)
