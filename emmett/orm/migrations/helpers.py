# -*- coding: utf-8 -*-
"""
    emmett.orm.migrations.helpers
    -----------------------------

    Provides helpers for migrations.

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

from collections.abc import Iterable
from uuid import uuid4

from ...datastructures import _unique_list


DEFAULT_VALUE = lambda: None


def make_migration_id():
    return uuid4().hex[-12:]


class WrappedOperation(object):
    def __init__(self, op_class, name, engine):
        self.op_class = op_class
        self.name = name
        self.engine = engine

    def __call__(self, *args, **kwargs):
        op = getattr(self.op_class, self.name)(*args, **kwargs)
        op._env_load_(self.engine)
        return op.run()


class Dispatcher(object):
    def __init__(self):
        self._registry = {}

    def dispatch_for(self, target):
        def wrap(fn):
            self._registry[target] = fn
            return fn
        return wrap

    def dispatch(self, obj):
        targets = type(obj).__mro__
        for target in targets:
            if target in self._registry:
                return self._registry[target]
        else:
            raise ValueError("no dispatch function for object: %s" % obj)


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
