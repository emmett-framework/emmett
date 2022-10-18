# -*- coding: utf-8 -*-
"""
    emmett.asgi.helpers
    -------------------

    Provides ASGI helpers

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

import ssl
import sys

from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple


class Registry:
    __slots__ = ["_data"]

    def __init__(self):
        self._data: Dict[str, Callable[..., Any]] = {}

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def keys(self) -> Iterable[str]:
        return self._data.keys()

    def register(self, key: str) -> Callable[[], Callable[..., Any]]:
        def wrap(builder: Callable[..., Any]) -> Callable[..., Any]:
            self._data[key] = builder
            return builder
        return wrap

    def get(self, key: str) -> Callable[..., Any]:
        try:
            return self._data[key]
        except KeyError:
            raise RuntimeError(f"'{key}' implementation not available.")



class BuilderRegistry(Registry):
    __slots__ = []

    def __init__(self):
        self._data: Dict[str, Tuple[Callable[..., Any], List[str]]] = {}

    def register(
        self,
        key: str,
        packages: Optional[List[str]] = None
    ) -> Callable[[], Callable[..., Any]]:
        packages = packages or []

        def wrap(builder: Callable[..., Any]) -> Callable[..., Any]:
            loaded_packages, implemented = {}, True
            try:
                for package in packages:
                    __import__(package)
                    loaded_packages[package] = sys.modules[package]
            except ImportError:
                implemented = False
            if implemented:
                self._data[key] = (builder, loaded_packages)
            return builder
        return wrap

    def get(self, key: str) -> Callable[..., Any]:
        try:
            builder, packages = self._data[key]
        except KeyError:
            raise RuntimeError(f"'{key}' implementation not available.")
        return builder(**packages)


class RequestCancelled(Exception):
    ...


def _create_ssl_context(
    certfile: str,
    keyfile: str,
    cert_reqs: int,
    ca_certs: Optional[str],
    alpn_protocols: List[str]
) -> ssl.SSLContext:
    ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    ctx.set_ciphers("ECDHE+AESGCM")
    ctx.options |= (
        ssl.OP_NO_SSLv2 |
        ssl.OP_NO_SSLv3 |
        ssl.OP_NO_TLSv1 |
        ssl.OP_NO_TLSv1_1 |
        ssl.OP_NO_COMPRESSION
    )
    ctx.set_alpn_protocols(alpn_protocols)
    ctx.load_cert_chain(certfile, keyfile)
    ctx.verify_mode = cert_reqs
    if ca_certs:
        ctx.load_verify_locations(ca_certs)
    return ctx
