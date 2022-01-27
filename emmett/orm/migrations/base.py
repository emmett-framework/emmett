# -*- coding: utf-8 -*-
"""
    emmett.orm.migrations.base
    --------------------------

    Provides base migrations objects.

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Dict, Type

from ...datastructures import sdict
from .. import Database, Model, Field
from .engine import MetaEngine, Engine
from .helpers import WrappedOperation, _feasible_as_dbms_default

if TYPE_CHECKING:
    from .operations import Operation


class Schema(Model):
    tablename = "emmett_schema"
    version = Field()


class Migration:
    _registered_ops_: Dict[str, Type[Operation]] = {}
    skip_on_compare: bool = False

    @classmethod
    def register_operation(
        cls,
        name: str
    ) -> Callable[[Type[Operation]], Type[Operation]]:
        def wrap(op_cls: Type[Operation]) -> Type[Operation]:
            cls._registered_ops_[name] = op_cls
            return op_cls
        return wrap

    def __init__(self, app: Any, db: Database, is_meta: bool = False):
        self.db = db
        if is_meta:
            self.engine = MetaEngine(db)
        else:
            self.engine = Engine(db)

    def __getattr__(self, name: str) -> WrappedOperation:
        registered = self._registered_ops_.get(name)
        if registered is not None:
            return WrappedOperation(registered, name, self.engine)
        raise NotImplementedError


class Column(sdict):
    def __init__(
        self,
        name: str,
        type: str = 'string',
        unique: bool = False,
        notnull: bool = False,
        **kwargs: Any
    ):
        self.name = name
        self.type = type
        self.unique = unique
        self.notnull = notnull
        for key, val in kwargs.items():
            self[key] = val
        self.length: int = self.length or 255

    def _fk_type(self, db: Database, tablename: str):
        if self.name not in db[tablename]._model_._belongs_ref_:
            return
        ref = db[tablename]._model_._belongs_ref_[self.name]
        if ref.ftype != 'id':
            self.type = ref.ftype
            self.length = db[ref.model][ref.fk].length
            self.on_delete = None

    @classmethod
    def from_field(cls, field: Field) -> Column:
        rv = cls(
            field.name,
            field._pydal_types.get(field._type, field._type),
            field.unique,
            field.notnull,
            length=field.length,
            ondelete=field.ondelete,
            **field._ormkw
        )
        if _feasible_as_dbms_default(field.default):
            rv.default = field.default
        rv._fk_type(field.db, field.tablename)
        return rv

    def __repr__(self) -> str:
        return "%s(%s)" % (
            self.__class__.__name__,
            ", ".join(["%s=%r" % (k, v) for k, v in self.items()])
        )
