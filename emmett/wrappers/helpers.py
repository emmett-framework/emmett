# -*- coding: utf-8 -*-
"""
    emmett.wrappers.helpers
    -----------------------

    Provides wrappers helpers.

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

import re

from typing import (
    BinaryIO,
    Dict,
    Iterable,
    Iterator,
    MutableMapping,
    Optional,
    Tuple,
    Union
)

from .._internal import loop_copyfileobj

regex_client = re.compile(r'[\w\-:]+(\.[\w\-]+)*\.?')


class ResponseHeaders(MutableMapping[str, str]):
    __slots__ = ['_data']

    def __init__(self, data: Optional[Dict[str, str]] = None):
        self._data = data or {}

    __hash__ = None  # type: ignore

    def __getitem__(self, key: str) -> str:
        return self._data[key.lower()]

    def __setitem__(self, key: str, value: str):
        self._data[key.lower()] = value

    def __delitem__(self, key: str):
        del self._data[key.lower()]

    def __contains__(self, key: str) -> bool:  # type: ignore
        return key.lower() in self._data

    def __iter__(self) -> Iterator[str]:
        for key in self._data.keys():
            yield key

    def __len__(self) -> int:
        return len(self._data)

    def items(self) -> Iterator[Tuple[str, str]]:  # type: ignore
        for key, value in self._data.items():
            yield key, value

    def keys(self) -> Iterator[str]:  # type: ignore
        for key in self._data.keys():
            yield key

    def values(self) -> Iterator[str]:  # type: ignore
        for value in self._data.values():
            yield value

    def update(self, data: Dict[str, str]):  # type: ignore
        self._data.update(data)


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
