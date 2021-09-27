# -*- coding: utf-8 -*-
"""
    emmett.orm.helpers
    ------------------

    Provides ORM helpers.

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

from __future__ import annotations

import re
import time

from functools import wraps
from typing import TYPE_CHECKING, Any, Callable

from pydal._globals import THREAD_LOCAL
from pydal.helpers.classes import Reference as _IDReference, ExecutionHandler
from pydal.objects import Field as _Field

from ..datastructures import sdict
from ..utils import cachedprop

if TYPE_CHECKING:
    from .objects import Table


class RowReferenceMeta:
    __slots__ = ['table', 'caster']

    def __init__(self, table: Table, caster: Callable[[Any], Any]):
        self.table = table
        self.caster = caster

    def fetch(self, val):
        return self.table._db(self.table._id == self.caster(val)).select(
            limitby=(0, 1),
            orderby_on_limitby=False
        ).first()


class RowReferenceMixin:
    def __allocate(self):
        if not self._refrecord:
            self._refrecord = self._refmeta.fetch(self)
        if not self._refrecord:
            raise RuntimeError(
                "Using a recursive select but encountered a broken " +
                "reference: %s %r" % (self._table, self)
            )

    def __getattr__(self, key: str) -> Any:
        if key == 'id':
            return self._refmeta.caster(self)
        if key in self._refmeta.table:
            self.__allocate()
        if self._refrecord:
            return self._refrecord.get(key, None)
        return None

    def get(self, key: str, default: Any = None) -> Any:
        return self.__getattr__(key, default)

    def __setattr__(self, key: str, value: Any):
        if key.startswith('_'):
            self._refmeta.caster.__setattr__(self, key, value)
            return
        self.__allocate()
        self._refrecord[key] = value

    def __getitem__(self, key):
        if key == 'id':
            return self._refmeta.caster(self)
        self.__allocate()
        return self._refrecord.get(key, None)

    def __setitem__(self, key, value):
        self.__allocate()
        self._refrecord[key] = value

    def __repr__(self) -> str:
        return repr(self._refmeta.caster(self))


class RowReferenceInt(RowReferenceMixin, int):
    def __new__(cls, id, table: Table, *args: Any, **kwargs: Any):
        rv = super().__new__(cls, id, *args, **kwargs)
        int.__setattr__(rv, '_refmeta', RowReferenceMeta(table, int))
        int.__setattr__(rv, '_refrecord', None)
        return rv


class RowReferenceStr(RowReferenceMixin, str):
    def __new__(cls, id, table: Table, *args: Any, **kwargs: Any):
        rv = super().__new__(cls, id, *args, **kwargs)
        str.__setattr__(rv, '_refmeta', RowReferenceMeta(table, str))
        str.__setattr__(rv, '_refrecord', None)
        return rv


class Reference(object):
    def __init__(self, *args, **params):
        self.reference = [arg for arg in args]
        self.params = params
        self.refobj[id(self)] = self

    def __call__(self, func):
        if self.__class__.__name__ not in ['has_one', 'has_many']:
            raise SyntaxError(
                '%s cannot be used as a decorator' % self.__class__.__name__)
        if not callable(func):
            raise SyntaxError('Argument must be callable')
        if self.reference:
            raise SyntaxError(
                "When using %s as decorator, you must use the 'field' option" %
                self.__class__.__name__)
        new_reference = {func.__name__: {'method': func}}
        field = self.params.get('field')
        if field:
            new_reference[func.__name__]['field'] = field
        cast = self.params.get('cast')
        if cast:
            new_reference[func.__name__]['cast'] = cast
        self.reference = [new_reference]
        return self

    @property
    def refobj(self):
        return {}


class ReferenceData(sdict):
    def __init__(self, model_class, **kwargs):
        self.model_class = model_class
        super(ReferenceData, self).__init__(**kwargs)

    @cachedprop
    def dbset(self):
        if self.method:
            return self.method(self.model_class)
        return self.model_class.db

    @cachedprop
    def model_instance(self):
        if self.method:
            return self.dbset._model_._instance_()
        return self.dbset[self.model]._model_

    @property
    def table(self):
        return self.model_instance.table

    @property
    def table_name(self):
        return self.model_instance.tablename

    @property
    def field_instance(self):
        return self.table[self.field]


class RelationBuilder(object):
    def __init__(self, ref, model_instance):
        self.ref = ref
        self.model = model_instance

    def _make_refid(self, row):
        return row.id if row is not None else self.model.id

    def _extra_scopes(self, ref, model_instance=None):
        model_instance = model_instance or ref.model_instance
        rv = []
        if ref.scope is not None:
            scope_m = model_instance._scopes_[ref.scope].f
            rv.append(lambda f=scope_m, m=model_instance: f(m))
        if ref.where is not None:
            rv.append(lambda f=ref.where, m=model_instance: f(m))
        return rv

    def _patch_query_with_scopes(self, ref, query):
        for scope in self._extra_scopes(ref):
            query = query & scope()
        return query

    def _patch_query_with_scopes_on(self, ref, query, model_name):
        model = self.model.db[model_name]._model_
        for scope in self._extra_scopes(ref, model):
            query = query & scope()
        return query

    def _get_belongs(self, modelname, value):
        return self.model.db[modelname]._model_._belongs_ref_.get(value)

    def belongs_query(self):
        return (self.model.table[self.ref[1]] == self.model.db[self.ref[0]].id)

    @staticmethod
    def many_query(ref, rid):
        if ref.cast and isinstance(rid, _Field):
            rid = rid.cast(ref.cast)
        return ref.model_instance.table[ref.field] == rid

    def _many(self, ref, rid):
        return ref.dbset.where(
            self._patch_query_with_scopes(ref, self.many_query(ref, rid))
        ).query

    def many(self, row=None):
        return self._many(self.ref, self._make_refid(row))

    def via(self, row=None):
        db = self.model.db
        rid = self._make_refid(row)
        sname = self.model.__class__.__name__
        stack = []
        midrel = self.model._hasmany_ref_[self.ref.via]
        stack.append(self.ref)
        while midrel.via is not None:
            stack.insert(0, midrel)
            midrel = self.model._hasmany_ref_[midrel.via]
        query = self._many(midrel, rid)
        step_model = midrel.table_name
        sel_field = db[step_model].ALL
        last_belongs = None
        last_via = None
        for via in stack:
            rname = via.field or via.name[:-1]
            belongs_model = self._get_belongs(step_model, rname)
            if belongs_model:
                #: join table way
                last_belongs = step_model
                last_via = via
                _query = (db[belongs_model.model].id == db[step_model][rname])
                sel_field = db[belongs_model.model].ALL
                step_model = belongs_model.model
            else:
                #: shortcut way
                last_belongs = None
                rname = via.field or via.name
                midrel = db[step_model]._model_._hasmany_ref_[rname]
                _query = self._many(midrel, db[step_model].id)
                step_model = midrel.table_name
                sel_field = db[step_model].ALL
            query = query & _query
        query = via.dbset.where(
            self._patch_query_with_scopes_on(via, query, step_model)).query
        return query, sel_field, sname, rid, last_belongs, last_via


class Callback(object):
    _inst_count_ = 0

    def __init__(self, f, t):
        self.t = []
        if isinstance(f, Callback):
            self.t += f.t
            f = f.f
        self.f = f
        self.t.append(t)
        self._inst_count_ = Callback._inst_count_
        Callback._inst_count_ += 1

    def __call__(self):
        return None


class JoinedIDReference(_IDReference):
    @classmethod
    def _from_record(cls, record, table=None):
        rv = cls(record.id)
        rv._table = table
        rv._record = record
        return rv

    def as_dict(self, datetime_to_str=False, custom_types=None):
        return self._record.as_dict()


class TimingHandler(ExecutionHandler):
    def _timings(self):
        THREAD_LOCAL._emtdal_timings_ = getattr(
            THREAD_LOCAL, '_emtdal_timings_', [])
        return THREAD_LOCAL._emtdal_timings_

    @cachedprop
    def timings(self):
        return self._timings()

    def before_execute(self, command):
        self.t = time.time()

    def after_execute(self, command):
        dt = time.time() - self.t
        self.timings.append((command, dt))


class ConnectionContext:
    __slots__ = ['db', 'conn', 'with_transaction', 'reuse_if_open']

    def __init__(self, db, with_transaction=True, reuse_if_open=True):
        self.db = db
        self.conn = None
        self.with_transaction = with_transaction
        self.reuse_if_open = reuse_if_open

    def __enter__(self):
        self.conn = self.db.connection_open(
            with_transaction=self.with_transaction,
            reuse_if_open=self.reuse_if_open
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            self.db.connection_close()
        self.conn = None

    async def __aenter__(self):
        self.conn = await self.db.connection_open_loop(
            with_transaction=self.with_transaction,
            reuse_if_open=self.reuse_if_open
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            await self.db.connection_close_loop()
        self.conn = None


def decamelize(name):
    return "_".join(re.findall('[A-Z][^A-Z]*', name)).lower()


def camelize(name):
    return "".join(w.capitalize() for w in name.split("_"))


def make_tablename(classname):
    return decamelize(classname) + "s"


def wrap_scope_on_set(dbset, model_instance, scope):
    @wraps(scope)
    def wrapped(*args, **kwargs):
        return dbset.where(
            scope(model_instance, *args, **kwargs),
            model=model_instance.__class__)
    return wrapped


def wrap_scope_on_model(scope):
    @wraps(scope)
    def wrapped(cls, *args, **kwargs):
        return cls.db.where(
            scope(cls._instance_(), *args, **kwargs), model=cls)
    return wrapped


def wrap_virtual_on_model(model, virtual):
    @wraps(virtual)
    def wrapped(row, *args, **kwargs):
        return virtual(model, row, *args, **kwargs)
    return wrapped


def typed_row_reference(id: Any, table: Table):
    return {
        'id': RowReferenceInt,
        'integer': RowReferenceInt,
        'string': RowReferenceStr
    }[table._id.type](id, table)
