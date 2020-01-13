# -*- coding: utf-8 -*-
"""
    emmett.asgi.protocols
    ---------------------

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

from ..helpers import BuilderRegistry


class ProtocolRegistry(BuilderRegistry):
    def get_protocol(self, name):
        try:
            builder, packages = self.builders[name]
        except KeyError:
            raise RuntimeError(
                'Porotocol "{}" not available'.format(name)
            )
        return _wrap_builder_with_packages(builder, packages)


class ProtocolWrapperRegistry(BuilderRegistry):
    def get_protocol(self, name):
        try:
            builder, packages = self.builders[name]
        except KeyError:
            raise RuntimeError(
                'Porotocol "{}" not available'.format(name)
            )
        return _wrap_builder_wrapper_with_packages(builder, packages)


# class Protocol(object):
#     def __init__(self, packages={}, *args, **kwargs):
#         for key, val in packages.items():
#             setattr(self, key, val)
#         self._init(*args, **kwargs)
#         self.init()

#     def _init(self, *args, **kwargs):
#         pass

#     def init(self):
#         pass


class ProtocolWrapper(object):
    def __init__(self, packages={}, *args, **kwargs):
        for key, val in packages.items():
            setattr(self, key, val)
        self._init(*args, **kwargs)

    def _init(self, *args, **kwargs):
        self._args = args
        self._kwargs = kwargs

    @classmethod
    def protocol_cls(cls):
        raise NotImplementedError

    def build_protocol(self):
        return self.protocol_cls()(*self._args, **self._kwargs)

    @classmethod
    def tick(cls):
        return cls.protocol_cls().tick()


def _wrap_builder_with_packages(builder, packages):
    def wrap(*args, **kwargs):
        return builder(packages=packages, *args, **kwargs)
    return wrap


class _wrap_builder_wrapper_with_packages(object):
    def __init__(self, builder, packages):
        self.builder = builder
        self.packages = packages

    def __call__(self, *args, **kwargs):
        return self.builder(
            packages=self.packages, *args, **kwargs).build_protocol()

    def tick(self):
        return self.builder.tick()


from .http import protocols as protocols_http
from .ws import protocols as protocols_ws
