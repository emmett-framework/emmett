# -*- coding: utf-8 -*-
"""
    emmett.wrappers.response
    ------------------------

    Provides response wrappers.

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

from http.cookies import Morsel, SimpleCookie
from typing import Any

from ..datastructures import sdict
from ..helpers import get_flashed_messages
from ..html import htmlescape
from ..utils import cachedprop
from . import Wrapper
from .helpers import ResponseHeaders

# Workaround for adding samesite support to pre 3.8 python
Morsel._reserved["samesite"] = "SameSite"  # type: ignore  # noqa


class Response(Wrapper):
    __slots__ = ('status', 'headers', 'cookies')

    def __init__(self):
        self.status = 200
        self.headers = ResponseHeaders({'content-type': 'text/plain'})
        self.cookies = SimpleCookie()

    @cachedprop
    def meta(self) -> sdict[str, Any]:
        return sdict()

    @cachedprop
    def meta_prop(self) -> sdict[str, Any]:
        return sdict()

    @property
    def content_type(self) -> str:
        return self.headers['content-type']

    @content_type.setter
    def content_type(self, value: str):
        self.headers['content-type'] = value

    def alerts(self, **kwargs):
        return get_flashed_messages(**kwargs)

    def _meta_tmpl(self):
        return [
            (key, htmlescape(val)) for key, val in self.meta.items()
        ]

    def _meta_tmpl_prop(self):
        return [
            (key, htmlescape(val)) for key, val in self.meta_prop.items()
        ]
