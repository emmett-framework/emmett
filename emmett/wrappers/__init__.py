# -*- coding: utf-8 -*-
"""
    emmett.wrappers
    ---------------

    Provides request and response wrappers.

    :copyright: (c) 2014-2019 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

from urllib.parse import parse_qs

from ..datastructures import sdict
from ..utils import cachedprop
from .helpers import Headers


class Wrapper:
    def __getitem__(self, key):
        return getattr(self, key, None)

    def __setitem__(self, key, value):
        setattr(self, key, value)


class ScopeWrapper(Wrapper):
    __slots__ = (
        '_scope', 'scheme', 'path', 'headers', 'host'
    )

    def __init__(self, scope):
        self._scope = scope
        self.scheme = scope['scheme']
        self.path = scope['emt.path']
        self.headers = Headers(scope)
        self.host = self.headers.get('host')

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
