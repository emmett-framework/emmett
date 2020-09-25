# -*- coding: utf-8 -*-
"""
    emmett.wrappers
    ---------------

    Provides request and response wrappers.

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

from __future__ import annotations

import re

from http.cookies import SimpleCookie
from typing import Any, List, Type, TypeVar, Union
from urllib.parse import parse_qs

from ..asgi.typing import Scope, Receive, Send
from ..datastructures import Accept, sdict
from ..language.helpers import LanguageAccept
from ..typing import T
from ..utils import cachedprop
from .helpers import Headers

AcceptType = TypeVar("AcceptType", bound=Accept)

_regex_accept = re.compile(r'''
    ([^\s;,]+(?:[ \t]*;[ \t]*(?:[^\s;,q][^\s;,]*|q[^\s;,=][^\s;,]*))*)
    (?:[ \t]*;[ \t]*q=(\d*(?:\.\d+)?)[^,]*)?''', re.VERBOSE)


class Wrapper:
    def __getitem__(self, name: str) -> Any:
        return getattr(self, name, None)

    def __setitem__(self, name: str, value: Any):
        setattr(self, name, value)


class ScopeWrapper(Wrapper):
    __slots__ = ('_scope', '_receive', '_send', 'scheme', 'path')

    def __init__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send
    ):
        self._scope = scope
        self._receive = receive
        self._send = send
        self.scheme: str = scope['scheme']
        self.path: str = scope['emt.path']

    def __parse_accept_header(
        self,
        value: str,
        cls: Type[AcceptType]
    ) -> AcceptType:
        if not value:
            return cls(None)
        result = []
        for match in _regex_accept.finditer(value):
            mq = match.group(2)
            if not mq:
                quality = 1.0
            else:
                quality = max(min(float(mq), 1), 0)
            result.append((match.group(1), quality))
        return cls(result)

    @cachedprop
    def headers(self) -> Headers:
        return Headers(self._scope)

    @cachedprop
    def host(self) -> str:
        return self.headers.get('host')

    @cachedprop
    def accept_language(self) -> LanguageAccept:
        return self.__parse_accept_header(
            self.headers.get('accept-language'), LanguageAccept
        )

    @cachedprop
    def cookies(self) -> SimpleCookie:
        cookies: SimpleCookie = SimpleCookie()
        for cookie in self.headers.get('cookie', '').split(';'):
            cookies.load(cookie)
        return cookies

    @cachedprop
    def query_params(self) -> sdict[str, Union[str, List[str]]]:
        rv: sdict[str, Any] = sdict()
        for key, values in parse_qs(
            self._scope['query_string'].decode('latin-1'), keep_blank_values=True
        ).items():
            if len(values) == 1:
                rv[key] = values[0]
                continue
            rv[key] = values
        return rv
