# -*- coding: utf-8 -*-

import asyncio
import json
import pendulum
import re

from cgi import FieldStorage, parse_header
from collections import Mapping
from http.cookies import SimpleCookie
from io import BytesIO
from urllib.parse import parse_qs

from ..datastructures import Accept, sdict
from ..language.helpers import LanguageAccept
from ..utils import cachedprop

_regex_accept = re.compile(r'''
    ([^\s;,]+(?:[ \t]*;[ \t]*(?:[^\s;,q][^\s;,]*|q[^\s;,=][^\s;,]*))*)
    (?:[ \t]*;[ \t]*q=(\d*(?:\.\d+)?)[^,]*)?''', re.VERBOSE)


class Body(object):
    __slots__ = ('_data', '_complete', '_max_content_length')

    def __init__(self, max_content_length=None):
        self._data = bytearray()
        self._complete = asyncio.Event()
        # self._has_data = asyncio.Event()
        self._max_content_length = max_content_length

    # def __aiter__(self):
    #     return self

    # async def __anext__(self) -> bytes:
    #     # If the first time through was the entirety of the data,
    #     # set_complete was already called so we have to wait on both
    #     # _has_data and _complete otherwise we'll hang indefinitely
    #     # waiting for _has_data since it will never get set again
    #     await asyncio.wait(
    #         [self._has_data.wait(), self._complete.wait()], return_when=asyncio.FIRST_COMPLETED,
    #     )
    #     if self._complete.is_set() and len(self._data) == 0:
    #         raise StopAsyncIteration()

    #     data = bytes(self._data)
    #     self._data.clear()
    #     self._has_data.clear()
    #     return data

    async def __await__(self):
        await self._complete.wait()
        return bytes(self._data)

    def append(self, data):
        if data == b'':
            return
        self._data.extend(data)
        # self._has_data.set()
        # if self._max_content_length is not None and len(self._data) > self._max_content_length:
        #     from ..exceptions import RequestEntityTooLarge  # noqa Avoiding circular import
        #     raise RequestEntityTooLarge()

    def set_complete(self):
        self._complete.set()
        # self._has_data.set()


class Headers(Mapping):
    __slots__ = ('_data',)

    def __init__(self, scope):
        # self._header_list = scope['headers']
        self._data = self.__parse_list(scope['headers'])

    @staticmethod
    def __parse_list(headers):
        rv = {}
        for key, val in headers:
            rv[key.decode()] = val.decode()
        return rv

    # @cachedprop
    # def _data(self):
    #     rv = {}
    #     for key, val in self._header_list:
    #         rv[key.decode()] = val.decode()
    #     return rv

    __hash__ = None

    def __getitem__(self, key):
        return self._data[key]

    def __contains__(self, key):
        return key in self._data

    def __iter__(self):
        for key, value in self._data.items():
            yield key, value

    def __len__(self):
        return len(self._data)

    def get(self, key, default=None, cast=None):
        rv = self._data.get(key, default)
        if cast is None:
            return rv
        try:
            return cast(rv)
        except ValueError:
            return default

    def items(self):
        return self._data.items()

    def keys(self):
        return self._data.keys()

    def values(self):
        return self._data.values()


class Request(object):
    def __init__(self, scope, max_content_length=None, body_timeout=None):
        self._scope = scope
        # print(scope)
        # print(scope)
        # print(type(scope['headers']))
        self.max_content_length = max_content_length
        self.body_timeout = body_timeout
        self.scheme = scope['scheme']
        # self.hostname = None
        self.method = scope['method']
        self.path = scope['emt.path']
        # if (
        #     self.content_length is not None and self.max_content_length is not None and
        #     self.content_length > self.max_content_length
        # ):
        #     from ..exceptions import RequestEntityTooLarge  # noqa Avoiding circular import
        #     raise RequestEntityTooLarge()
        # self._input = Body(self.max_content_length)
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
        try:
            print('ensuring body_future')
            body_future = asyncio.ensure_future(self._input)
            rv = await asyncio.wait_for(body_future, timeout=self.body_timeout)
        except asyncio.TimeoutError:
            body_future.cancel()
            # from ..exceptions import RequestTimeout
            # raise RequestTimeout()
            raise
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
        if self._empty_body_methods.get(self.method):
            return sdict()
        return await self._load_params()

    def _load_params_missing(self, data):
        return sdict()

    def _load_params_json(self, data):
        rv = sdict()
        json_data = json.loads(data)
        rv.update(json_data)
        return rv

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
        if not self.content_type:
            return sdict()
        loader = self._params_loaders.get(
            self.content_type, self._load_params_missing)
        return loader(self, await self.body)

    @cachedprop
    def accept_language(self):
        return self.__parse_accept_header(
            self.headers.get('accept-language'), LanguageAccept)
