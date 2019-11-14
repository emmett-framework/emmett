# -*- coding: utf-8 -*-
"""
    weppy.wrappers.helpers
    ----------------------

    Provides wrappers helpers.

    :copyright: (c) 2014-2019 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

from collections.abc import Mapping


class Headers(Mapping):
    __slots__ = ('_data')

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
        return self._data[key.lower()]

    def __contains__(self, key):
        return key in self._data

    def __iter__(self):
        for key, value in self._data.items():
            yield key, value

    def __len__(self):
        return len(self._data)

    def get(self, key, default=None, cast=None):
        rv = self._data.get(key.lower(), default)
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
