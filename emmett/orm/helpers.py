# -*- coding: utf-8 -*-
"""
    emmett.orm.helpers
    ------------------

    Provides ORM helpers.

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

from __future__ import annotations

import copyreg
import operator
import re
import time

from functools import reduce, wraps
from typing import TYPE_CHECKING, Any, Callable

from pydal._globals import THREAD_LOCAL
from pydal.helpers.classes import ExecutionHandler
from pydal.objects import Field as _Field

from ..datastructures import sdict
from ..utils import cachedprop

if TYPE_CHECKING:
    from .objects import Table


class RowReferenceMeta:
    __slots__ = ['table', 'pk', 'caster']

    def __init__(self, table: Table, caster: Callable[[Any], Any]):
        self.table = table
        self.pk = table._id.name
        self.caster = caster

    def fetch(self, val):
        return self.table._db(self.table._id == self.caster(val)).select(
            limitby=(0, 1),
            orderby_on_limitby=False
        ).first()


class RowReferenceMultiMeta:
    __slots__ = ['table', 'pks', 'pks_idx', 'caster', 'casters']
    _casters = {'integer': int, 'string': str}

    def __init__(self, table: Table) -> None:
        self.table = table
        self.pks = list(table._primarykey)
        self.pks_idx = {key: idx for idx, key in enumerate(self.pks)}
        self.caster = tuple
        self.casters = {pk: self._casters[table[pk].type] for pk in self.pks}

    def fetch(self, val):
        query = reduce(
            operator.and_, [
                self.table[pk] == self.casters[pk](self.caster.__getitem__(val, idx))
                for pk, idx in self.pks_idx.items()
            ]
        )
        return self.table._db(query).select(
            limitby=(0, 1),
            orderby_on_limitby=False
        ).first()


class RowReferenceMixin:
    def _allocate_(self):
        if not self._refrecord:
            self._refrecord = self._refmeta.fetch(self)
        if not self._refrecord:
            raise RuntimeError(
                "Using a recursive select but encountered a broken " +
                "reference: %s %r" % (self._table, self)
            )

    def __getattr__(self, key: str) -> Any:
        if key == self._refmeta.pk:
            return self._refmeta.caster(self)
        if key in self._refmeta.table:
            self._allocate_()
        if self._refrecord:
            return self._refrecord.get(key, None)
        return None

    def get(self, key: str, default: Any = None) -> Any:
        return self.__getattr__(key, default)

    def __setattr__(self, key: str, value: Any):
        if key.startswith('_'):
            self._refmeta.caster.__setattr__(self, key, value)
            return
        self._allocate_()
        self._refrecord[key] = value

    def __getitem__(self, key):
        if key == self._refmeta.pk:
            return self._refmeta.caster(self)
        self._allocate_()
        return self._refrecord.get(key, None)

    def __setitem__(self, key, value):
        self._allocate_()
        self._refrecord[key] = value

    def __pure__(self):
        return self._refmeta.caster(self)

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


class RowReferenceMulti(RowReferenceMixin, tuple):
    def __new__(cls, id, table: Table, *args: Any, **kwargs: Any):
        tupid = tuple(id[key] for key in table._primarykey)
        rv = super().__new__(cls, tupid, *args, **kwargs)
        tuple.__setattr__(rv, '_refmeta', RowReferenceMultiMeta(table))
        tuple.__setattr__(rv, '_refrecord', None)
        return rv

    def __getattr__(self, key: str) -> Any:
        if key in self._refmeta.pks:
            return self._refmeta.casters[key](
                tuple.__getitem__(self, self._refmeta.pks_idx[key])
            )
        if key in self._refmeta.table:
            self._allocate_()
        if self._refrecord:
            return self._refrecord.get(key, None)
        return None

    def __getitem__(self, key):
        if key in self._refmeta.pks:
            return self._refmeta.casters[key](
                tuple.__getitem__(self, self._refmeta.pks_idx[key])
            )
        self._allocate_()
        return self._refrecord.get(key, None)


class GeoFieldWrapper(str):
    _rule_parens = re.compile(r"^(\(+)(?:.+)$")
    _json_geom_map = {
        "POINT": "Point",
        "LINESTRING": "LineString",
        "POLYGON": "Polygon",
        "MULTIPOINT": "MultiPoint",
        "MULTILINESTRING": "MultiLineString",
        "MULTIPOLYGON": "MultiPolygon"
    }

    def __new__(cls, value, *args: Any, **kwargs: Any):
        geometry, raw_coords = value.strip()[:-1].split("(", 1)
        rv = super().__new__(cls, value, *args, **kwargs)
        coords = cls._parse_coords_block(raw_coords)
        str.__setattr__(rv, '_geometry', geometry.strip())
        str.__setattr__(rv, '_coordinates', coords)
        return rv

    @classmethod
    def _parse_coords_block(cls, v):
        groups = []
        parens_match = cls._rule_parens.match(v)
        parens = parens_match.group(1) if parens_match else ''
        if parens:
            for element in v.split(parens):
                if not element:
                    continue
                element = element.strip()
                shift = -2 if element.endswith(",") else -1
                groups.append(f"{parens}{element}"[1:shift])
        if not groups:
            return cls._parse_coords_group(v)
        return tuple(
            cls._parse_coords_block(group) for group in groups
        )

    @staticmethod
    def _parse_coords_group(v):
        accum = []
        for element in v.split(","):
            accum.append(tuple(float(v) for v in element.split(" ")))
        return tuple(accum) if len(accum) > 1 else accum[0]

    def _repr_coords(self, val=None):
        val = val or self._coordinates
        if isinstance(val[0], tuple):
            accum = []
            for el in val:
                inner, plevel = self._repr_coords(el)
                inner = f"({inner})" if not plevel else inner
                accum.append(inner)
            return ",".join(accum), False
        return "%f %f" % val, True

    @property
    def geometry(self):
        return self._geometry

    @property
    def coordinates(self):
        return self._coordinates

    @property
    def groups(self):
        if not self._geometry.startswith("MULTI"):
            return tuple()
        return tuple(
            self.__class__(f"{self._geometry[5:]}({self._repr_coords(coords)[0]})")
            for coords in self._coordinates
        )

    def __json__(self):
        return {
            "type": self._json_geom_map[self._geometry],
            "coordinates": self._coordinates
        }


class PasswordFieldWrapper(str):
    _emt_field_hashed_contents_ = True


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
    def fields_instances(self):
        return tuple(
            self.table[field]
            for field in self.model_instance._belongs_fks_.get(
                self.reverse, sdict(local_fields=[self.reverse])
            ).local_fields
        )


class RelationBuilder(object):
    def __init__(self, ref, model_instance):
        self.ref = ref
        self.model = model_instance

    def _make_refid(self, row):
        pks = self.model.primary_keys or ["id"]
        if row:
            return tuple(row[pk] for pk in pks)
        return tuple(self.model.table[pk] for pk in pks)

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
        return self.model.db[modelname]._model_._belongs_fks_.get(value)

    def belongs_query(self):
        return reduce(
            operator.and_, [
                self.model.table[local] == self.model.db[self.ref.model][foreign]
                for local, foreign in self.ref.coupled_fields
            ]
        )

    @staticmethod
    def many_query(ref, rid):
        components = rid
        if ref.cast:
            components = []
            for element in rid:
                if isinstance(rid, _Field):
                    components.append(element.cast(ref.cast))
                else:
                    components.append(element)
        return reduce(
            operator.and_, [
                field == components[idx]
                for idx, field in enumerate(ref.fields_instances)
            ]
        )

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
        midrel = self.model._hasmany_ref_.get(
            self.ref.via,
            self.model._hasone_ref_.get(self.ref.via)
        )
        stack.append(self.ref)
        while midrel.via is not None:
            stack.insert(0, midrel)
            midrel = self.model._hasmany_ref_.get(
                midrel.via,
                self.model._hasone_ref_.get(midrel.via)
            )
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
                _query = reduce(
                    operator.and_, [
                        (
                            db[belongs_model.model][foreign] ==
                            db[step_model][local]
                        ) for local, foreign in belongs_model.coupled_fields
                    ]
                )
                sel_field = db[belongs_model.model].ALL
                step_model = belongs_model.model
            else:
                #: shortcut way
                last_belongs = None
                rname = via.field or via.name
                midrel = db[step_model]._model_._hasmany_ref_.get(
                    rname,
                    db[step_model]._model_._hasone_ref_.get(rname)
                )
                if midrel.via:
                    nested = RelationBuilder(midrel, midrel.model_class)
                    nested_data = nested.via()
                    _query = nested_data[0]
                    step_model = midrel.model_class.tablename
                else:
                    _query = self._many(
                        midrel, [
                            db[step_model][step_field]
                            for step_field in (
                                db[step_model]._model_.primary_keys or ["id"]
                            )
                        ]
                    )
                    step_model = midrel.table_name
                sel_field = db[step_model].ALL
            query = query & _query
        query = via.dbset.where(
            self._patch_query_with_scopes_on(via, query, step_model)
        ).query
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
    field_type = table._id.type if table._id else None
    return {
        'id': RowReferenceInt,
        'integer': RowReferenceInt,
        'string': RowReferenceStr,
        None: RowReferenceMulti
    }[field_type](id, table)


def typed_row_reference_from_record(record: Any, model: Any):
    field_type = model.table._id.type if model.table._id else None
    refcls = {
        'id': RowReferenceInt,
        'integer': RowReferenceInt,
        'string': RowReferenceStr,
        None: RowReferenceMulti
    }[field_type]
    if len(model._fieldset_pk) > 1:
        id = {pk: record[pk] for pk in model._fieldset_pk}
    else:
        id = record[tuple(model._fieldset_pk)[0]]
    rv = refcls(id, model.table)
    rv._refrecord = record
    return rv


def _rowref_pickler(obj):
    return obj._refmeta.caster, (obj.__pure__(), )


copyreg.pickle(RowReferenceInt, _rowref_pickler)
copyreg.pickle(RowReferenceStr, _rowref_pickler)
copyreg.pickle(RowReferenceMulti, _rowref_pickler)
