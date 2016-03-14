# -*- coding: utf-8 -*-
"""
    weppy.dal.migrations.generation
    -------------------------------

    Provides generation utils for migrations.

    :copyright: (c) 2014-2016 by Giovanni Barillari

    Based on the code of Alembic (https://bitbucket.org/zzzeek/alembic)
    :copyright: (c) 2009-2015 by Michael Bayer

    :license: BSD, see LICENSE for more details.
"""

from collections import OrderedDict
from ..._compat import itervalues
from ...datastructures import OrderedSet
from .base import Column
from .helpers import Dispatcher, DEFAULT_VALUE, _feasible_as_dbms_default
from .operations import UpgradeOps, CreateTableOp, DropTableOp, \
    AddColumnOp, DropColumnOp, AlterColumnOp


class MetaTable(object):
    def __init__(self, name, columns=[], **kw):
        self.name = name
        self.columns = OrderedDict()
        for column in columns:
            self.columns[column.name] = column
        self.kw = kw

    @property
    def fields(self):
        return list(self.columns)

    def __getitem__(self, name):
        return self.columns[name]

    def __setitem__(self, name, value):
        self.columns[name] = value

    def __delitem__(self, name):
        del self.columns[name]

    def __repr__(self):
        return "Table(%r, %s)" % (
            self.name,
            ", ".join(["%s" % column for column in itervalues(self.columns)])
        )


class MetaData(object):
    def __init__(self):
        self.tables = {}

    def create_table(self, name, columns, **kw):
        self.tables[name] = MetaTable(name, columns)

    def drop_table(self, name):
        del self.tables[name]

    def add_column(self, table, column):
        self.tables[table][column.name] = column

    def drop_column(self, table, column):
        del self.tables[table][column]

    def change_column(self, table_name, column_name, changes):
        self.tables[table_name][column_name].update(**changes)


class Comparator(object):
    def __init__(self, db, meta):
        self.db = db
        self.meta = meta

    def make_ops(self):
        self.ops = []
        self.tables()
        return self.ops

    def _build_metatable(self, dbtable):
        columns = []
        for field in list(dbtable):
            columns.append(Column.from_field(field))
        return MetaTable(
            dbtable._tablename,
            columns
        )

    def tables(self):
        db_table_names = OrderedSet([t._tablename for t in self.db])
        meta_table_names = OrderedSet(list(self.meta.tables))
        # : new tables
        for table_name in db_table_names.difference(meta_table_names):
            self.ops.append(
                CreateTableOp.from_table(
                    self._build_metatable(self.db[table_name])))
        # : removed tables
        for table_name in meta_table_names.difference(db_table_names):
            self.ops.append(DropTableOp.drop_table(table_name))
        # : existing tables
        for table_name in meta_table_names.intersection(db_table_names):
            self.columns(
                self.db[table_name], self.meta.tables[table_name])
            self.table(
                self.db[table_name], self.meta.tables[table_name])

    def table(self, dbtable, metatable):
        self.indexes_and_uniques(dbtable, metatable)
        self.foreign_keys(dbtable, metatable)

    def indexes_and_uniques(self, dbtable, metatable):
        # TODO
        pass

    def foreign_keys(self, dbtable, metatable):
        # TODO
        pass

    def columns(self, dbtable, metatable):
        db_column_names = OrderedSet([fname for fname in dbtable.fields])
        meta_column_names = OrderedSet(metatable.fields)
        # : new columns
        for column_name in db_column_names.difference(meta_column_names):
            self.ops.append(AddColumnOp.from_column_and_tablename(
                dbtable._tablename, Column.from_field(dbtable[column_name])))
        # : existing columns
        for column_name in meta_column_names.intersection(db_column_names):
            self.ops.append(AlterColumnOp(dbtable._tablename, column_name))
            self.column(
                dbtable[column_name], metatable.columns[column_name])
            if not self.ops[-1].has_changes():
                self.ops.pop()
        # : removed columns
        for column_name in meta_column_names.difference(db_column_names):
            self.ops.append(
                DropColumnOp.drop_column(dbtable._tablename, column_name))

    def column(self, dbcolumn, metacolumn):
        self.notnulls(dbcolumn, metacolumn)
        self.types(dbcolumn, metacolumn)
        self.defaults(dbcolumn, metacolumn)

    def types(self, dbcolumn, metacolumn):
        self.ops[-1].existing_type = metacolumn.type
        if dbcolumn.type != metacolumn.type:
            self.ops[-1].modify_type = dbcolumn.type

    def notnulls(self, dbcolumn, metacolumn):
        self.ops[-1].existing_notnull = metacolumn.notnull
        if dbcolumn.notnull != metacolumn.notnull:
            self.ops[-1].modify_notnull = dbcolumn.notnull

    def defaults(self, dbcolumn, metacolumn):
        oldv, newv = metacolumn.default, dbcolumn.default
        self.ops[-1].existing_default = oldv
        if newv != oldv:
            if not all(callable(v) for v in [oldv, newv]):
                if _feasible_as_dbms_default(newv):
                    self.ops[-1].modify_default = newv

    @classmethod
    def compare(cls, db, meta):
        ops = cls(db, meta).make_ops()
        return UpgradeOps(ops)


class Generator(object):
    def __init__(self, db, scriptdir, head):
        self.db = db
        self.scriptdir = scriptdir
        self.head = head
        self.meta = MetaData()
        self._load_head_to_meta()

    def _load_head_to_meta(self):
        for revision in self.scriptdir.walk_revisions("base", self.head):
            migration = revision.migration_class(
                None, self.meta, is_meta=True)
            migration.up()

    def generate(self):
        return Comparator.compare(self.db, self.meta)

    @classmethod
    def generate_from(cls, dal, scriptdir, head):
        return cls(dal, scriptdir, head).generate()


class Renderer(object):
    def render_op(self, op):
        op_renderer = renderers.dispatch(op)
        return op_renderer(op)

    def render_opcontainer(self, op_container):
        rv = []
        if not op_container.ops:
            rv.append("pass")
        else:
            for op in op_container.ops:
                rv.append(self.render_op(op))
        return rv

    @classmethod
    def render_migration(cls, migration_op):
        r = cls()
        return r.render_opcontainer(migration_op.upgrade_ops), \
            r.render_opcontainer(migration_op.downgrade_ops)


renderers = Dispatcher()


@renderers.dispatch_for(CreateTableOp)
def _add_table(op):
    table = op.to_table()

    args = [
        col for col in [
            _render_column(col) for col in itervalues(table.columns)]
        if col
    ]
    # + sorted([
    #     rcons for rcons in [
    #         _render_constraint(cons) for cons in table.constraints]
    #         if rcons is not None
    #     ]
    # )
    indent = " " * 12

    if len(args) > 255:
        args = '*[' + (',\n' + indent).join(args) + ']'
    else:
        args = (',\n' + indent).join(args)

    text = ("self.create_table(\n" + indent + "%(tablename)r,\n" + indent +
            "%(args)s") % {
        'tablename': op.table_name,
        'args': args
    }
    for k in sorted(op.kw):
        text += ",\n" + indent + "%s=%r" % (k.replace(" ", "_"), op.kw[k])
    text += ")"
    return text


@renderers.dispatch_for(DropTableOp)
def _drop_table(op):
    text = "self.drop_table(%(tname)r" % {
        "tname": op.table_name
    }
    text += ")"
    return text


def _render_column(column):
    opts = []

    if column.default is not None:
        opts.append(("default", column.default))

    # if not column.autoincrement:
    #     opts.append(("autoincrement", column.autoincrement))

    if column.notnull:
        opts.append(("notnull", column.notnull))

    if column.type in ("string", "password", "upload"):
        opts.append(("length", column.length))
    elif column.type.startswith(('reference', 'big-reference')):
        opts.append(("ondelete", column.ondelete))

    kw_str = ""
    if opts:
        kw_str = ", %s" % \
            ", ".join(["%s=%r" % (key, val) for key, val in opts])
    return "migrations.Column(%(name)r, %(type)r%(kw)s)" % {
        'name': column.name,
        'type': column.type,
        'kw': kw_str
    }


@renderers.dispatch_for(AddColumnOp)
def _add_column(op):
    return "self.add_column(%(tname)r, %(column)s)" % {
        "tname": op.table_name,
        "column": _render_column(op.column)
    }


@renderers.dispatch_for(DropColumnOp)
def _drop_column(op):
    return "self.drop_column(%(tname)r, %(cname)r)" % {
        "tname": op.table_name,
        "column": op.column_name
    }


@renderers.dispatch_for(AlterColumnOp)
def _alter_column(op):
    indent = " " * 12
    text = "self.alter_column(%(tname)r, %(cname)r" % {
        'tname': op.table_name,
        'cname': op.column_name}

    if op.existing_type is not None:
        text += ",\n%sexisting_type=%r" % (indent, op.existing_type)
    if op.modify_default is not DEFAULT_VALUE:
        text += ",\n%sdefault=%r" % (indent, op.modify_default)
    if op.modify_type is not None:
        text += ",\n%stype=%r" % (indent, op.modify_type)
    if op.modify_notnull is not None:
        text += ",\n%snotnull=%r" % (indent, op.modify_notnull)
    if op.modify_notnull is None and op.existing_notnull is not None:
        text += ",\n%sexisting_notnull=%r" % (indent, op.existing_notnull)
    if op.modify_default is DEFAULT_VALUE and op.existing_default:
        text += ",\n%sexisting_default=%s" % (indent, op.existing_default)

    text += ")"
    return text
