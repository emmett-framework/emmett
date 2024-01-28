# -*- coding: utf-8 -*-
"""
    emmett.http
    -----------

    Provides the HTTP interfaces.

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

from __future__ import annotations

import errno
import os
import stat

from email.utils import formatdate
from hashlib import md5
from typing import Any, AsyncIterable, BinaryIO, Dict, Generator, Iterable, Tuple

from granian.rsgi import HTTPProtocol

from ._internal import loop_open_file
from .ctx import current
from .libs.contenttype import contenttype


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


class HTTPResponse(Exception):
    def __init__(
        self,
        status_code: int,
        *,
        headers: Dict[str, str] = {'content-type': 'text/plain'},
        cookies: Dict[str, Any] = {}
    ):
        self.status_code: int = status_code
        self._headers: Dict[str, str] = headers
        self._cookies: Dict[str, Any] = cookies

    @property
    def headers(self) -> Generator[Tuple[bytes, bytes], None, None]:
        for key, val in self._headers.items():
            yield key.encode('latin-1'), val.encode('latin-1')
        for cookie in self._cookies.values():
            yield b'set-cookie', str(cookie)[12:].encode('latin-1')

    @property
    def rsgi_headers(self) -> Generator[Tuple[str, str], None, None]:
        for key, val in self._headers.items():
            yield key, val
        for cookie in self._cookies.values():
            yield 'set-cookie', str(cookie)[12:]

    async def _send_headers(self, send):
        await send({
            'type': 'http.response.start',
            'status': self.status_code,
            'headers': list(self.headers)
        })

    async def _send_body(self, send):
        await send({'type': 'http.response.body'})

    async def asgi(self, scope, send):
        await self._send_headers(send)
        await self._send_body(send)

    def rsgi(self, protocol: HTTPProtocol):
        protocol.response_empty(
            self.status_code,
            list(self.rsgi_headers)
        )


class HTTPBytes(HTTPResponse):
    def __init__(
        self,
        status_code: int,
        body: bytes = b'',
        headers: Dict[str, str] = {'content-type': 'text/plain'},
        cookies: Dict[str, Any] = {}
    ):
        super().__init__(status_code, headers=headers, cookies=cookies)
        self.body = body

    async def _send_body(self, send):
        await send({
            'type': 'http.response.body',
            'body': self.body,
            'more_body': False
        })

    def rsgi(self, protocol: HTTPProtocol):
        protocol.response_bytes(
            self.status_code,
            list(self.rsgi_headers),
            self.body
        )


class HTTP(HTTPResponse):
    def __init__(
        self,
        status_code: int,
        body: str = '',
        headers: Dict[str, str] = {'content-type': 'text/plain'},
        cookies: Dict[str, Any] = {}
    ):
        super().__init__(status_code, headers=headers, cookies=cookies)
        self.body = body

    @property
    def encoded_body(self):
        return self.body.encode('utf-8')

    async def _send_body(self, send):
        await send({
            'type': 'http.response.body',
            'body': self.encoded_body,
            'more_body': False
        })

    def rsgi(self, protocol: HTTPProtocol):
        protocol.response_str(
            self.status_code,
            list(self.rsgi_headers),
            self.body
        )


class HTTPRedirect(HTTPResponse):
    def __init__(
        self,
        status_code: int,
        location: str,
        cookies: Dict[str, Any] = {}
    ):
        location = location.replace('\r', '%0D').replace('\n', '%0A')
        super().__init__(
            status_code,
            headers={'location': location},
            cookies=cookies
        )


class HTTPFile(HTTPResponse):
    def __init__(
        self,
        file_path: str,
        headers: Dict[str, str] = {},
        cookies: Dict[str, Any] = {},
        chunk_size: int = 4096
    ):
        super().__init__(200, headers=headers, cookies=cookies)
        self.file_path = file_path
        self.chunk_size = chunk_size

    def _get_stat_headers(self, stat_data):
        content_length = str(stat_data.st_size)
        last_modified = formatdate(stat_data.st_mtime, usegmt=True)
        etag_base = str(stat_data.st_mtime) + '_' + str(stat_data.st_size)
        etag = md5(etag_base.encode('utf-8')).hexdigest()
        return {
            'content-type': contenttype(self.file_path),
            'content-length': content_length,
            'last-modified': last_modified,
            'etag': etag
        }

    async def asgi(self, scope, send):
        try:
            stat_data = os.stat(self.file_path)
            if not stat.S_ISREG(stat_data.st_mode):
                await HTTP(403).send(scope, send)
                return
            self._headers.update(self._get_stat_headers(stat_data))
            await self._send_headers(send)
            if 'http.response.pathsend' in scope.get('extensions', {}):
                await send({
                    'type': 'http.response.pathsend',
                    'path': str(self.file_path)
                })
            else:
                await self._send_body(send)
        except IOError as e:
            if e.errno == errno.EACCES:
                await HTTP(403).send(scope, send)
            else:
                await HTTP(404).send(scope, send)

    async def _send_body(self, send):
        async with loop_open_file(self.file_path, mode='rb') as f:
            more_body = True
            while more_body:
                chunk = await f.read(self.chunk_size)
                more_body = len(chunk) == self.chunk_size
                await send({
                    'type': 'http.response.body',
                    'body': chunk,
                    'more_body': more_body,
                })

    def rsgi(self, protocol: HTTPProtocol):
        try:
            stat_data = os.stat(self.file_path)
            if not stat.S_ISREG(stat_data.st_mode):
                return HTTP(403).rsgi(protocol)
            self._headers.update(self._get_stat_headers(stat_data))
        except IOError as e:
            if e.errno == errno.EACCES:
                return HTTP(403).rsgi(protocol)
            return HTTP(404).rsgi(protocol)

        protocol.response_file(
            self.status_code,
            list(self.rsgi_headers),
            self.file_path
        )


class HTTPIO(HTTPResponse):
    def __init__(
        self,
        io_stream: BinaryIO,
        headers: Dict[str, str] = {},
        cookies: Dict[str, Any] = {},
        chunk_size: int = 4096
    ):
        super().__init__(200, headers=headers, cookies=cookies)
        self.io_stream = io_stream
        self.chunk_size = chunk_size

    def _get_io_headers(self):
        content_length = str(self.io_stream.getbuffer().nbytes)
        return {
            'content-length': content_length
        }

    async def asgi(self, scope, send):
        self._headers.update(self._get_io_headers())
        await self._send_headers(send)
        await self._send_body(send)

    async def _send_body(self, send):
        more_body = True
        while more_body:
            chunk = self.io_stream.read(self.chunk_size)
            more_body = len(chunk) == self.chunk_size
            await send({
                'type': 'http.response.body',
                'body': chunk,
                'more_body': more_body,
            })

    def rsgi(self, protocol: HTTPProtocol):
        protocol.response_bytes(
            self.status_code,
            list(self.rsgi_headers),
            self.io_stream.read()
        )


class HTTPIter(HTTPResponse):
    def __init__(
        self,
        iter: Iterable[bytes],
        headers: Dict[str, str] = {},
        cookies: Dict[str, Any] = {}
    ):
        super().__init__(200, headers=headers, cookies=cookies)
        self.iter = iter

    async def _send_body(self, send):
        for chunk in self.iter:
            await send({
                'type': 'http.response.body',
                'body': chunk,
                'more_body': True
            })
        await send({'type': 'http.response.body', 'body': b'', 'more_body': False})

    async def rsgi(self, protocol: HTTPProtocol):
        trx = protocol.response_stream(
            self.status_code,
            list(self.rsgi_headers)
        )
        for chunk in self.iter:
            await trx.send_bytes(chunk)


class HTTPAiter(HTTPResponse):
    def __init__(
        self,
        iter: AsyncIterable[bytes],
        headers: Dict[str, str] = {},
        cookies: Dict[str, Any] = {}
    ):
        super().__init__(200, headers=headers, cookies=cookies)
        self.iter = iter

    async def _send_body(self, send):
        async for chunk in self.iter:
            await send({
                'type': 'http.response.body',
                'body': chunk,
                'more_body': True
            })
        await send({'type': 'http.response.body', 'body': b'', 'more_body': False})

    async def rsgi(self, protocol: HTTPProtocol):
        trx = protocol.response_stream(
            self.status_code,
            list(self.rsgi_headers)
        )
        async for chunk in self.iter:
            await trx.send_bytes(chunk)


def redirect(location: str, status_code: int = 303):
    response = current.response
    response.status = status_code
    raise HTTPRedirect(status_code, location, response.cookies)
