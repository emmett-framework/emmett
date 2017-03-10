# -*- coding: utf-8 -*-
"""
    weppy.orm.migrations.base
    -------------------------

    Provides base migrations objects.

    :copyright: (c) 2014-2017 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

from ..._compat import iteritems
from ...datastructures import sdict
from .. import Model, Field
from .engine import MetaEngine, Engine
from .helpers import WrappedOperation, _feasible_as_dbms_default


class Schema(Model):
    tablename = "weppy_schema"
    version = Field()


class Migration(object):
    _registered_ops_ = {}

    @classmethod
    def register_operation(cls, name):
        def wrap(op_cls):
            cls._registered_ops_[name] = op_cls
            return op_cls
        return wrap

    def __init__(self, app, db, is_meta=False):
        self.db = db
        if is_meta:
            self.engine = MetaEngine(db)
        else:
            self.engine = Engine(db)

    def __getattr__(self, name):
        registered = self._registered_ops_.get(name)
        if registered is not None:
            return WrappedOperation(registered, name, self.engine)
        else:
            raise NotImplementedError


class Column(sdict):
    def __init__(self, name, type='string', unique=False, notnull=False,
                 **kwargs):
        self.name = name
        self.type = type
        self.unique = unique
        self.notnull = notnull
        for key, val in iteritems(kwargs):
            self[key] = val
        self.length = self.length or 255

    def _build_fks(self, db, tablename):
        if self.type.startswith(('reference', 'big-reference')):
            if self.type.startswith('reference'):
                referenced = self.type[10:].strip()
            else:
                referenced = self.type[14:].strip()
            try:
                rtablename, rfieldname = referenced.split('.')
            except:
                rtablename = referenced
                rfieldname = 'id'
            if not rtablename:
                rtablename = tablename
            rtable = db[rtablename]
            rfield = rtable[rfieldname]
            if getattr(rtable, '_primarykey', None) and rfieldname in \
                    rtable._primarykey or rfield.unique:
                if not rfield.unique and len(rtable._primarykey) > 1:
                    # self.tfk = [pk for pk in rtable._primarykey]
                    raise NotImplementedError(
                        'Column of type reference pointing to multiple ' +
                        'columns are currently not supported.'
                    )
                else:
                    self.fk = True

    @classmethod
    def from_field(cls, field):
        rv = cls(
            field.name,
            field.type,
            field.unique,
            field.notnull,
            length=field.length,
            ondelete=field.ondelete
        )
        if _feasible_as_dbms_default(field.default):
            rv.default = field.default
        rv._build_fks(field.db, field.tablename)
        return rv

    def __repr__(self):
        return "%s(%s)" % (
            self.__class__.__name__,
            ", ".join(["%s=%r" % (k, v) for k, v in iteritems(self)])
        )
