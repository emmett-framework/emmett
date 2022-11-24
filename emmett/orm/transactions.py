# -*- coding: utf-8 -*-
"""
    emmett.orm.transactions
    -----------------------

    Provides pyDAL advanced transactions implementation for Emmett.

    :copyright: 2014 Giovanni Barillari

    Parts of this code are inspired to peewee
    :copyright: (c) 2010 by Charles Leifer

    :license: BSD-3-Clause
"""

import uuid

from functools import wraps


class callable_context_manager(object):
    def __call__(self, fn):
        @wraps(fn)
        def inner(*args, **kwargs):
            with self:
                return fn(*args, **kwargs)
        return inner


class _atomic(callable_context_manager):
    def __init__(self, adapter):
        self.adapter = adapter

    def __enter__(self):
        if self.adapter.transaction_depth() == 0:
            self._helper = self.adapter.db.transaction()
        else:
            self._helper = self.adapter.db.savepoint()
        return self._helper.__enter__()

    def __exit__(self, exc_type, exc_val, exc_tb):
        return self._helper.__exit__(exc_type, exc_val, exc_tb)


class _transaction(callable_context_manager):
    def __init__(self, adapter, lock_type=None):
        self.adapter = adapter
        self._lock_type = lock_type
        self._ops = []

    def _add_op(self, op):
        self._ops.append(op)

    def _add_ops(self, ops):
        self._ops.extend(ops)

    def _begin(self):
        if self._lock_type:
            self.adapter.begin(self._lock_type)
        else:
            self.adapter.begin()

    def commit(self, begin=True):
        for op in self._ops:
            for callback in op.table._before_commit:
                callback(op.op_type, op.context)
            for callback in getattr(op.table, f"_before_commit_{op.op_type}"):
                callback(op.context)
        self.adapter.commit()
        for op in self._ops:
            for callback in op.table._after_commit:
                callback(op.op_type, op.context)
            for callback in getattr(op.table, f"_after_commit_{op.op_type}"):
                callback(op.context)
        self._ops.clear()
        if begin:
            self._begin()

    def rollback(self, begin=True):
        self._ops.clear()
        self.adapter.rollback()
        if begin:
            self._begin()

    def __enter__(self):
        if self.adapter.transaction_depth() == 0:
            self._begin()
        self.adapter.push_transaction(self)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if exc_type:
                self.rollback(False)
            elif self.adapter.transaction_depth() == 1:
                try:
                    self.commit(False)
                except Exception:
                    self.rollback(False)
                    raise
        finally:
            self.adapter.pop_transaction()


class _savepoint(callable_context_manager):
    def __init__(self, adapter, sid=None):
        self.adapter = adapter
        self.sid = sid or 's' + uuid.uuid4().hex
        self.quoted_sid = self.adapter.dialect.quote(self.sid)
        self._ops = []
        self._parent = None

    def _add_op(self, op):
        self._ops.append(op)

    def _add_ops(self, ops):
        self._ops.extend(ops)

    def _begin(self):
        self.adapter.execute('SAVEPOINT %s;' % self.quoted_sid)

    def commit(self, begin=True):
        self.adapter.execute('RELEASE SAVEPOINT %s;' % self.quoted_sid)
        if begin:
            self._begin()

    def rollback(self):
        self._ops.clear()
        self.adapter.execute('ROLLBACK TO SAVEPOINT %s;' % self.quoted_sid)

    def __enter__(self):
        self._parent = self.adapter.top_transaction()
        self._begin()
        self.adapter.push_transaction(self)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if exc_type:
                self.rollback()
            else:
                try:
                    self.commit(begin=False)
                    if self._parent:
                        self._parent._add_ops(self._ops)
                except Exception:
                    self.rollback()
                    raise
        finally:
            self.adapter.pop_transaction()
