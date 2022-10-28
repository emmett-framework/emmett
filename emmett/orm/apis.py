# -*- coding: utf-8 -*-
"""
    emmett.orm.apis
    ---------------

    Provides ORM apis.

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

from collections import OrderedDict
from enum import Enum
from typing import List

from .errors import MissingFieldsForCompute
from .helpers import Reference, Callback


class belongs_to(Reference):
    _references_ = OrderedDict()

    @property
    def refobj(self):
        return belongs_to._references_


class refers_to(Reference):
    _references_ = OrderedDict()

    @property
    def refobj(self):
        return refers_to._references_


class has_one(Reference):
    _references_ = OrderedDict()

    @property
    def refobj(self):
        return has_one._references_


class has_many(Reference):
    _references_ = OrderedDict()

    @property
    def refobj(self):
        return has_many._references_


class compute(object):
    _inst_count_ = 0

    def __init__(self, field_name: str, watch: List[str] = []):
        self.field_name = field_name
        self.watch_fields = set(watch)
        self._inst_count_ = compute._inst_count_
        compute._inst_count_ += 1

    def __call__(self, f):
        self.f = f
        return self

    def compute(self, model, op_row):
        if self.watch_fields:
            row_keyset = set(op_row.keys())
            if row_keyset & self.watch_fields:
                if not self.watch_fields.issubset(row_keyset):
                    raise MissingFieldsForCompute(
                        f"Compute field '{self.field_name}' missing required "
                        f"({','.join(self.watch_fields - row_keyset)})"
                    )
            else:
                return
        return self.f(model, op_row)


class rowattr(object):
    _inst_count_ = 0

    def __init__(self, field_name):
        self.field_name = field_name
        self._inst_count_ = rowattr._inst_count_
        rowattr._inst_count_ += 1

    def __call__(self, f):
        self.f = f
        return self


class rowmethod(rowattr):
    pass


def before_insert(f):
    return Callback(f, '_before_insert')


def after_insert(f):
    return Callback(f, '_after_insert')


def before_update(f):
    return Callback(f, '_before_update')


def after_update(f):
    return Callback(f, '_after_update')


def before_delete(f):
    return Callback(f, '_before_delete')


def after_delete(f):
    return Callback(f, '_after_delete')


def before_save(f):
    return Callback(f, '_before_save')


def after_save(f):
    return Callback(f, '_after_save')


def before_destroy(f):
    return Callback(f, '_before_destroy')


def after_destroy(f):
    return Callback(f, '_after_destroy')


def before_commit(f):
    return Callback(f, '_before_commit')


def after_commit(f):
    return Callback(f, '_after_commit')


def _commit_callback_op(kind, op):
    def _deco(f):
        return Callback(f, f'_{kind}_commit_{op}')
    return _deco


before_commit.operation = lambda op: _commit_callback_op('before', op)
after_commit.operation = lambda op: _commit_callback_op('after', op)


class scope(object):
    def __init__(self, name):
        self.name = name

    def __call__(self, f):
        self.f = f
        return self
