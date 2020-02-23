# -*- coding: utf-8 -*-
"""
    emmett.wrappers.request
    -----------------------

    Provides http request wrappers.

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

import asyncio
import pendulum
import re

from cgi import FieldStorage, parse_header
from datetime import datetime
from io import BytesIO
from urllib.parse import parse_qs
from typing import Optional

from ..asgi.typing import Scope, Receive, Send
from ..datastructures import sdict
from ..http import HTTP
from ..parsers import Parsers
from ..utils import cachedprop
from . import ScopeWrapper
from .helpers import FileStorage, RequestCancelled

_regex_client = re.compile(r'[\w\-:]+(\.[\w\-]+)*\.?')


class Body:
    __slots__ = ('_data', '_receive', '_max_content_length')

    def __init__(self, receive, max_content_length=None):
        self._data = bytearray()
        self._receive = receive
        self._max_content_length = max_content_length

    def append(self, data: bytes):
        if data == b'':
            return
        self._data.extend(data)
        if (
            self._max_content_length is not None and
            len(self._data) > self._max_content_length
        ):
            raise HTTP(413, 'Request entity too large')

    async def __load(self) -> bytes:
        while True:
            event = await self._receive()
            if event['type'] == 'http.request':
                self.append(event['body'])
                if not event.get('more_body', False):
                    break
            elif event['type'] == 'http.disconnect':
                raise RequestCancelled
        return bytes(self._data)

    def __await__(self):
        return self.__load().__await__()


class Request(ScopeWrapper):
    __slots__ = ['_now', 'method']

    def __init__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
        max_content_length: Optional[int] = None,
        body_timeout: Optional[int] = None
    ):
        super().__init__(scope, receive, send)
        self.max_content_length = max_content_length
        self.body_timeout = body_timeout
        self._now = datetime.utcnow()
        self.method = scope['method']

    @cachedprop
    def _input(self):
        return Body(self._receive, self.max_content_length)

    @cachedprop
    async def body(self):
        if (
            self.max_content_length and
            self.content_length > self.max_content_length
        ):
            raise HTTP(413, 'Request entity too large')
        try:
            rv = await asyncio.wait_for(self._input, timeout=self.body_timeout)
        except asyncio.TimeoutError:
            raise HTTP(408, 'Request timeout')
        return rv

    @cachedprop
    def now(self):
        return pendulum.instance(self._now)

    @cachedprop
    def now_local(self):
        return self.now.in_timezone(pendulum.local_timezone())

    @cachedprop
    def content_type(self):
        return parse_header(self.headers.get('content-type', ''))[0]

    @cachedprop
    def content_length(self):
        return self.headers.get('content_length', 0, cast=int)

    _empty_body_methods = {v: v for v in ['GET', 'HEAD', 'OPTIONS']}

    @cachedprop
    async def _input_params(self):
        if self._empty_body_methods.get(self.method) or not self.content_type:
            return sdict(), sdict()
        return await self._load_params()

    @cachedprop
    async def body_params(self):
        rv, _ = await self._input_params
        return rv

    @cachedprop
    async def files(self):
        _, rv = await self._input_params
        return rv

    def _load_params_missing(self, data):
        return sdict(), sdict()

    def _load_params_json(self, data):
        try:
            params = Parsers.get_for('json')(data)
        except Exception:
            params = {}
        return sdict(params), sdict()

    def _load_params_form_urlencoded(self, data):
        rv = sdict()
        for key, values in parse_qs(
            data.decode(), keep_blank_values=True
        ).items():
            if len(values) == 1:
                rv[key] = values[0]
                continue
            rv[key] = values
        return rv, sdict()

    def _load_params_form_multipart(self, data):
        params, files = sdict(), sdict()
        field_storage = FieldStorage(
            BytesIO(data),
            headers=self.headers,
            environ={'REQUEST_METHOD': self.method},
            keep_blank_values=True
        )
        for key in field_storage:
            field = field_storage[key]
            if isinstance(field, list):
                if len(field) > 1:
                    params[key] = []
                    for element in field:
                        params[key].append(element.value)
                else:
                    params[key] = field[0].value
            elif (
                isinstance(field, FieldStorage) and
                field.filename is not None
            ):
                files[key] = FileStorage(
                    BytesIO(field.file.read()),
                    field.filename,
                    field.name,
                    field.type,
                    field.headers
                )
                continue
            else:
                params[key] = field.value
        return params, files

    _params_loaders = {
        'application/json': _load_params_json,
        'application/x-www-form-urlencoded': _load_params_form_urlencoded,
        'multipart/form-data': _load_params_form_multipart
    }

    async def _load_params(self):
        loader = self._params_loaders.get(
            self.content_type, self._load_params_missing)
        return loader(self, await self.body)

    @cachedprop
    def client(self):
        g = _regex_client.search(self.headers.get('x-forwarded-for', ''))
        client = (g.group() or '').split(',')[0] if g else None
        if client in (None, '', 'unknown'):
            g = _regex_client.search(self.headers.get('remote-addr', ''))
            if g:
                client = g.group()
            elif self.host.startswith('['):
                # IPv6
                client = '::1'
            else:
                # IPv4
                client = '127.0.0.1'
        return client
