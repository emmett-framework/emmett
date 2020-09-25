# -*- coding: utf-8 -*-
"""
    emmett.wrappers.helpers
    -----------------------

    Provides wrappers helpers.

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

from typing import (
    Any,
    BinaryIO,
    Callable,
    Dict,
    Iterable,
    Iterator,
    Mapping,
    MutableMapping,
    Optional,
    Tuple,
    Union
)

from .._internal import loop_copyfileobj


class Headers(Mapping[str, str]):
    __slots__ = ["_data"]

    def __init__(self, scope: Dict[str, Any]):
        self._data: Dict[bytes, bytes] = {
            key: val for key, val in scope["headers"]
        }

    __hash__ = None  # type: ignore

    def __getitem__(self, key: str) -> str:
        return self._data[key.lower().encode("latin-1")].decode("latin-1")

    def __contains__(self, key: str) -> bool:  # type: ignore
        return key.lower().encode("latin-1") in self._data

    def __iter__(self) -> Iterator[str]:
        for key in self._data.keys():
            yield key.decode("latin-1")

    def __len__(self) -> int:
        return len(self._data)

    def get(
        self,
        key: str,
        default: Optional[Any] = None,
        cast: Optional[Callable[[Any], Any]] = None
    ) -> Any:
        rv = self._data.get(key.lower().encode("latin-1"))
        rv = rv.decode() if rv is not None else default  # type: ignore
        if cast is None:
            return rv
        try:
            return cast(rv)
        except ValueError:
            return default

    def items(self) -> Iterator[Tuple[str, str]]:  # type: ignore
        for key, value in self._data.items():
            yield key.decode("latin-1"), value.decode("latin-1")

    def keys(self) -> Iterator[str]:  # type: ignore
        for key in self._data.keys():
            yield key.decode("latin-1")

    def values(self) -> Iterator[str]:  # type: ignore
        for value in self._data.values():
            yield value.decode("latin-1")


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


class RequestCancelled(Exception):
    pass
