# -*- coding: utf-8 -*-
"""
    emmett.wrappers.request
    -----------------------

    Provides http request wrappers.

    :copyright: (c) 2014-2019 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

import asyncio
import pendulum
import re

from cgi import FieldStorage, parse_header
from http.cookies import SimpleCookie
from io import BytesIO
from urllib.parse import parse_qs

from ..datastructures import Accept, sdict
from ..http import HTTP
from ..language.helpers import LanguageAccept
from ..parsers import Parsers
from ..utils import cachedprop
from . import Wrapper
from .helpers import Headers

_regex_accept = re.compile(r'''
    ([^\s;,]+(?:[ \t]*;[ \t]*(?:[^\s;,q][^\s;,]*|q[^\s;,=][^\s;,]*))*)
    (?:[ \t]*;[ \t]*q=(\d*(?:\.\d+)?)[^,]*)?''', re.VERBOSE)
_regex_client = re.compile(r'[\w\-:]+(\.[\w\-]+)*\.?')


class Body(object):
    __slots__ = ('_data', '_complete', '_max_content_length')

    def __init__(self, max_content_length=None):
        self._data = bytearray()
        self._complete = asyncio.Event()
        self._max_content_length = max_content_length

    async def __load(self):
        await self._complete.wait()
        return bytes(self._data)

    def __await__(self):
        return self.__load().__await__()

    def append(self, data):
        if data == b'':
            return
        self._data.extend(data)
        if (
            self._max_content_length is not None and
            len(self._data) > self._max_content_length
        ):
            raise HTTP(413, 'Request entity too large')

    def set_complete(self):
        self._complete.set()


class Request(Wrapper):
    def __init__(self, scope, max_content_length=None, body_timeout=None):
        self._scope = scope
        self.max_content_length = max_content_length
        self.body_timeout = body_timeout
        self.scheme = scope['scheme']
        self.method = scope['method']
        self.path = scope['emt.path']
        self._input = scope['emt.input']
        self.headers = Headers(scope)
        self.host = self.headers.get('host')

    def __parse_accept_header(self, value, cls=Accept):
        if not value:
            return cls(None)
        result = []
        for match in _regex_accept.finditer(value):
            quality = match.group(2)
            if not quality:
                quality = 1
            else:
                quality = max(min(float(quality), 1), 0)
            result.append((match.group(1), quality))
        return cls(result)

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
        return pendulum.instance(self._scope['emt.now'])

    @cachedprop
    def now_local(self):
        return self.now.in_timezone(pendulum.local_timezone())

    @cachedprop
    def content_type(self):
        return parse_header(self.headers.get('content-type', ''))[0]

    @cachedprop
    def content_length(self):
        return self.headers.get('content_length', 0, cast=int)

    @cachedprop
    def query_params(self):
        rv = sdict()
        for key, values in parse_qs(
            self._scope['query_string'].decode('ascii'), keep_blank_values=True
        ).items():
            if len(values) == 1:
                rv[key] = values[0]
                continue
            rv[key] = values
        return rv

    @cachedprop
    def cookies(self):
        cookies = SimpleCookie()
        for cookie in self.headers.get('cookie', '').split(';'):
            cookies.load(cookie)
        return cookies

    _empty_body_methods = {v: v for v in ['GET', 'HEAD', 'OPTIONS']}

    @cachedprop
    async def body_params(self):
        if self._empty_body_methods.get(self.method) or not self.content_type:
            return sdict()
        return await self._load_params()

    @staticmethod
    def _load_params_missing(self, data):
        return sdict()

    def _load_params_json(self, data):
        try:
            params = Parsers.get_for('json')(data)
        except Exception:
            params = {}
        return sdict(params)

    def _load_params_form_urlencoded(self, data):
        rv = sdict()
        for key, values in parse_qs(
            data.decode(), keep_blank_values=True
        ).items():
            if len(values) == 1:
                rv[key] = values[0]
                continue
            rv[key] = values
        return rv

    # TODO: files
    def _load_params_form_multipart(self, data):
        rv = sdict()
        field_storage = FieldStorage(
            BytesIO(data), headers=self.headers,
            environ={'REQUEST_METHOD': self.method},
            keep_blank_values=True
        )
        for key in field_storage:
            field = field_storage[key]
            if isinstance(field, list):
                if len(field) > 1:
                    rv[key] = []
                    for element in field:
                        rv[key].append(element.value)
                else:
                    rv[key] = field[0].value
            elif (
                isinstance(field, FieldStorage) and
                field.filename is not None
            ):
                # self._files[key] = FileStorage(  # type: ignore
                #     io.BytesIO(field.file.read()), field.filename,
                #     field.name, field.type, field.headers,  # type: ignore # noqa: E501
                # )
                continue
            else:
                rv[key] = field.value
        return rv

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
    def accept_language(self):
        return self.__parse_accept_header(
            self.headers.get('accept-language'), LanguageAccept)

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
