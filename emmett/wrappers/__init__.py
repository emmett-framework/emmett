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

from abc import ABCMeta, abstractmethod
from http.cookies import SimpleCookie
from typing import Any, List, Mapping, Type, TypeVar, Union

from ..datastructures import Accept, sdict
from ..language.helpers import LanguageAccept
from ..typing import T
from ..utils import cachedprop

AcceptType = TypeVar("AcceptType", bound=Accept)

_regex_accept = re.compile(r'''
    ([^\s;,]+(?:[ \t]*;[ \t]*(?:[^\s;,q][^\s;,]*|q[^\s;,=][^\s;,]*))*)
    (?:[ \t]*;[ \t]*q=(\d*(?:\.\d+)?)[^,]*)?''', re.VERBOSE)


class Wrapper:
    def __getitem__(self, name: str) -> Any:
        return getattr(self, name, None)

    def __setitem__(self, name: str, value: Any):
        setattr(self, name, value)


class IngressWrapper(Wrapper, metaclass=ABCMeta):
    __slots__ = ['scheme', 'path']

    scheme: str
    path: str

    @property
    @abstractmethod
    def headers(self) -> Mapping[str, str]: ...

    @cachedprop
    def host(self) -> str:
        return self.headers.get('host')

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

    @property
    @abstractmethod
    def query_params(self) -> sdict[str, Union[str, List[str]]]: ...
