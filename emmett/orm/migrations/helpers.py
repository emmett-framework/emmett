# -*- coding: utf-8 -*-
"""
    emmett.orm.migrations.helpers
    -----------------------------

    Provides helpers for migrations.

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

from __future__ import annotations

from collections.abc import Iterable
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Callable, Dict, Generator, Type
from uuid import uuid4

from pydal.adapters.base import BaseAdapter

from ...datastructures import _unique_list
from .base import Database

if TYPE_CHECKING:
    from .engine import MetaEngine
    from .operations import Operation


DEFAULT_VALUE = lambda: None


def make_migration_id():
    return uuid4().hex[-12:]


class WrappedOperation:
    def __init__(self, op_class: Type[Operation], name: str, engine: MetaEngine):
        self.op_class = op_class
        self.name = name
        self.engine = engine

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        op = getattr(self.op_class, self.name)(*args, **kwargs)
        op._env_load_(self.engine)
        return op.run()


class Dispatcher:
    def __init__(self):
        self._registry: Dict[Type[Operation], Callable[[Operation], str]] = {}

    def dispatch_for(
        self,
        target: Type[Operation]
    ) -> Callable[[Callable[[Operation], str]], Callable[[Operation], str]]:
        def wrap(fn: Callable[[Operation], str]) -> Callable[[Operation], str]:
            self._registry[target] = fn
            return fn
        return wrap

    def dispatch(self, obj: Operation):
        targets = type(obj).__mro__
        for target in targets:
            if target in self._registry:
                return self._registry[target]
        raise ValueError(f"no dispatch function for object: {obj}")


class DryRunAdapter:
    def __init__(self, adapter: BaseAdapter, logger: Any):
        self.adapter = adapter
        self.__dlogger = logger

    def __getattr__(self, name: str) -> Any:
        return getattr(self.adapter, name)

    def execute(self, sql: str):
        self.__dlogger(sql)


class DryRunDatabase:
    def __init__(self, db: Database, logger: Any):
        self.db = db
        self._adapter = DryRunAdapter(db._adapter, logger)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.db, name)

    def __getitem__(self, key: str) -> Any:
        return self.db[key]

    @contextmanager
    def connection(self, *args: Any, **kwargs: Any) -> Generator[None, None, None]:
        yield None


def to_tuple(x, default=None):
    if x is None:
        return default
    elif isinstance(x, str):
        return (x, )
    elif isinstance(x, Iterable):
        return tuple(x)
    else:
        return (x, )


def tuple_or_value(val):
    if not val:
        return None
    elif len(val) == 1:
        return val[0]
    else:
        return val


def tuple_rev_as_scalar(rev):
    if not rev:
        return None
    elif len(rev) == 1:
        return rev[0]
    else:
        return rev


def dedupe_tuple(tup):
    return tuple(_unique_list(tup))


def format_with_comma(value):
    if value is None:
        return ""
    elif isinstance(value, str):
        return value
    elif isinstance(value, Iterable):
        return ", ".join(value)
    else:
        raise ValueError("Don't know how to comma-format %r" % value)


def _feasible_as_dbms_default(val):
    if callable(val):
        return False
    if val is None:
        return True
    if isinstance(val, int):
        return True
    if isinstance(val, str):
        return True
    if isinstance(val, (bool, float)):
        return True
    return False
