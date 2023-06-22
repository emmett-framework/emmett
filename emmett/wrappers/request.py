# -*- coding: utf-8 -*-
"""
    emmett.wrappers.request
    -----------------------

    Provides http request wrappers.

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

from abc import abstractmethod
from cgi import FieldStorage, parse_header
from io import BytesIO
from urllib.parse import parse_qs
from typing import Any

import pendulum

from ..datastructures import sdict
from ..parsers import Parsers
from ..utils import cachedprop
from . import IngressWrapper
from .helpers import FileStorage


class Request(IngressWrapper):
    __slots__ = ['_now', 'method']

    method: str

    @property
    @abstractmethod
    async def body(self) -> bytes: ...

    @cachedprop
    def now(self) -> pendulum.DateTime:
        return pendulum.instance(self._now)

    @cachedprop
    def now_local(self) -> pendulum.DateTime:
        return self.now.in_timezone(pendulum.local_timezone())  # type: ignore

    @cachedprop
    def content_type(self) -> str:
        return parse_header(self.headers.get('content-type', ''))[0]

    @cachedprop
    def content_length(self) -> int:
        return self.headers.get('content_length', 0, cast=int)

    _empty_body_methods = {v: v for v in ['GET', 'HEAD', 'OPTIONS']}

    @cachedprop
    async def _input_params(self):
        if self._empty_body_methods.get(self.method) or not self.content_type:
            return sdict(), sdict()
        return await self._load_params()

    @cachedprop
    async def body_params(self) -> sdict[str, Any]:
        rv, _ = await self._input_params
        return rv

    @cachedprop
    async def files(self) -> sdict[str, FileStorage]:
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
            data.decode('latin-1'), keep_blank_values=True
        ).items():
            if len(values) == 1:
                rv[key] = values[0]
                continue
            rv[key] = values
        return rv, sdict()

    @property
    def _multipart_headers(self):
        return self.headers

    @staticmethod
    def _file_param_from_field(field):
        return FileStorage(
            BytesIO(field.file.read()),
            field.filename,
            field.name,
            field.type,
            field.headers
        )

    def _load_params_form_multipart(self, data):
        params, files = sdict(), sdict()
        field_storage = FieldStorage(
            BytesIO(data),
            headers=self._multipart_headers,
            environ={'REQUEST_METHOD': self.method},
            keep_blank_values=True
        )
        for key in field_storage:
            field = field_storage[key]
            if isinstance(field, list):
                if len(field) > 1:
                    pvalues, fvalues = [], []
                    for item in field:
                        if item.filename is not None:
                            fvalues.append(self._file_param_from_field(item))
                        else:
                            pvalues.append(item.value)
                    if pvalues:
                        params[key] = pvalues
                    if fvalues:
                        files[key] = fvalues
                    continue
                else:
                   field = field[0]
            if field.filename is not None:
                files[key] = self._file_param_from_field(field)
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

    @abstractmethod
    async def push_promise(self, path: str): ...
