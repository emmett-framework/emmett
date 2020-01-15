# -*- coding: utf-8 -*-
"""
    emmett.wrappers.helpers
    -----------------------

    Provides wrappers helpers.

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

from collections.abc import Mapping
from typing import Any, BinaryIO, Dict, Iterable, Iterator, List, Tuple, Union

from .._internal import loop_copyfileobj


class Headers(Mapping):
    __slots__ = ('_data')

    def __init__(self, scope: Dict):
        self._data = self.__parse_list(scope['headers'])

    @staticmethod
    def __parse_list(headers: List[Tuple[bytes, bytes]]) -> Dict[str, str]:
        rv = {}
        for key, val in headers:
            rv[key.decode()] = val.decode()
        return rv

    __hash__ = None

    def __getitem__(self, key: str) -> str:
        return self._data[key.lower()]

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def __iter__(self) -> Iterator[Tuple[str, str]]:
        for key, value in self._data.items():
            yield key, value

    def __len__(self) -> int:
        return len(self._data)

    def get(self, key, default=None, cast=None) -> Any:
        rv = self._data.get(key.lower(), default)
        if cast is None:
            return rv
        try:
            return cast(rv)
        except ValueError:
            return default

    def items(self) -> Iterable[Tuple[str, str]]:
        return self._data.items()

    def keys(self) -> Iterable[str]:
        return self._data.keys()

    def values(self) -> Iterable[str]:
        return self._data.values()


class FileStorage:
    __slots__ = ('stream', 'filename', 'name', 'headers', 'content_type')

    def __init__(
        self,
        stream: BinaryIO,
        filename: str,
        name: str = None,
        content_type: str = None,
        headers: Dict = None
    ):
        self.stream = stream
        self.filename = filename
        self.name = name
        self.headers = headers or {}
        self.content_type = content_type or self.headers.get('content-type')

    @property
    def content_length(self) -> int:
        return int(self.headers.get('content-length', 0))

    async def save(
        self,
        destination: Union[BinaryIO, str],
        buffer_size: int = 16384
    ):
        close_destination = False
        if isinstance(destination, str):
            destination = open(destination, 'wb')
            close_destination = True
        try:
            await loop_copyfileobj(self.stream, destination, buffer_size)
        finally:
            if close_destination:
                destination.close()

    def __iter__(self) -> Iterable[bytes]:
        return iter(self.stream)

    def __repr__(self) -> str:
        return (
            f'<{self.__class__.__name__}: '
            f'{self.filename} ({self.content_type})')
