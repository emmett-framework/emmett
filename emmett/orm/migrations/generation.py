# -*- coding: utf-8 -*-
"""
    emmett.orm.migrations.generation
    --------------------------------

    Provides generation utils for migrations.

    :copyright: 2014 Giovanni Barillari

    Based on the code of Alembic (https://bitbucket.org/zzzeek/alembic)
    :copyright: (c) 2009-2015 by Michael Bayer

    :license: BSD-3-Clause
"""

from collections import OrderedDict

from ...datastructures import OrderedSet
from .base import Column
from .helpers import Dispatcher, DEFAULT_VALUE, _feasible_as_dbms_default
from .operations import UpgradeOps, CreateTableOp, DropTableOp, \
    AddColumnOp, DropColumnOp, AlterColumnOp, CreateIndexOp, DropIndexOp


class MetaTable(object):
    def __init__(self, name, columns=[], indexes=[], **kw):
        self.name = name
        self.columns = OrderedDict()
        for column in columns:
            self.columns[column.name] = column
        self.indexes = {}
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
            ", ".join(["%s" % column for column in self.columns.values()])
        )


class MetaIndex(object):
    def __init__(self, table_name, name, fields, expressions, unique, **kw):
        self.table_name = table_name
        self.name = name
        self.fields = fields
        self.expressions = expressions
        self.unique = unique
        self.kw = kw

    @property
    def where(self):
        return self.kw.get('where')

    def __repr__(self):
        opts = [('expressions', self.expressions), ('unique', self.unique)]
        for key, val in self.kw.items():
            opts.append((key, val))
        return "Index(%r, %r, %s)" % (
            self.name, self.fields,
            ", ".join(["%s=%r" % (opt[0], opt[1]) for opt in opts])
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

    def create_index(
        self, table_name, index_name, fields, expressions, unique, **kw
    ):
        self.tables[table_name].indexes[index_name] = MetaIndex(
            table_name, index_name, fields, expressions, unique, **kw
        )

    def drop_index(self, table_name, index_name):
        del self.tables[table_name].indexes[index_name]


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

    def _build_metaindex(self, dbtable, index_name):
        model = dbtable._model_
        dbindex = model._indexes_[index_name]
        kw = {}
        with self.db._adapter.index_expander():
            if 'where' in dbindex:
                kw['where'] = str(dbindex['where'])
            rv = MetaIndex(
                model.tablename, index_name,
                [field for field in dbindex['fields']],
                [str(expr) for expr in dbindex['expressions']],
                dbindex['unique'], **kw
            )
        return rv

    def tables(self):
        db_table_names = OrderedSet([t._tablename for t in self.db])
        meta_table_names = OrderedSet(list(self.meta.tables))
        #: new tables
        for table_name in db_table_names.difference(meta_table_names):
            meta_table = self._build_metatable(self.db[table_name])
            self.ops.append(CreateTableOp.from_table(meta_table))
            self.indexes_and_uniques(self.db[table_name], meta_table)
        #: removed tables
        for table_name in meta_table_names.difference(db_table_names):
            #: remove table indexes too
            metatable = self.meta.tables[table_name]
            for idx_name, idx in metatable.indexes.items():
                self.ops.append(DropIndexOp.from_index(idx))
            #: remove table
            self.ops.append(
                DropTableOp.from_table(self.meta.tables[table_name]))
        #: existing tables
        for table_name in meta_table_names.intersection(db_table_names):
            self.columns(
                self.db[table_name], self.meta.tables[table_name])
            self.table(
                self.db[table_name], self.meta.tables[table_name])

    def table(self, dbtable, metatable):
        self.indexes_and_uniques(dbtable, metatable)
        self.foreign_keys(dbtable, metatable)

    def indexes_and_uniques(self, dbtable, metatable, ops_stack=None):
        ops = ops_stack if ops_stack is not None else self.ops
        db_index_names = OrderedSet(
            [idxname for idxname in dbtable._model_._indexes_.keys()])
        meta_index_names = OrderedSet(list(metatable.indexes))
        #: removed indexes
        for index_name in meta_index_names.difference(db_index_names):
            ops.append(DropIndexOp.from_index(metatable.indexes[index_name]))
        #: new indexs
        for index_name in db_index_names.difference(meta_index_names):
            ops.append(
                CreateIndexOp.from_index(
                    self._build_metaindex(dbtable, index_name)))
        #: existing indexes
        for index_name in meta_index_names.intersection(db_index_names):
            metaindex = metatable.indexes[index_name]
            dbindex = self._build_metaindex(dbtable, index_name)
            if any(
                getattr(metaindex, key) != getattr(dbindex, key)
                for key in ['fields', 'expressions', 'unique', 'kw']
            ):
                ops.append(DropIndexOp.from_index(metaindex))
                ops.append(CreateIndexOp.from_index(dbindex))
        # TODO: uniques

    def foreign_keys(self, dbtable, metatable, ops_stack=None):
        # TODO
        pass

    def columns(self, dbtable, metatable):
        db_column_names = OrderedSet([fname for fname in dbtable.fields])
        meta_column_names = OrderedSet(metatable.fields)
        #: new columns
        for column_name in db_column_names.difference(meta_column_names):
            self.ops.append(AddColumnOp.from_column_and_tablename(
                dbtable._tablename, Column.from_field(dbtable[column_name])))
        #: existing columns
        for column_name in meta_column_names.intersection(db_column_names):
            self.ops.append(AlterColumnOp(dbtable._tablename, column_name))
            self.column(
                dbtable[column_name], metatable.columns[column_name])
            if not self.ops[-1].has_changes():
                self.ops.pop()
        #: removed columns
        for column_name in meta_column_names.difference(db_column_names):
            self.ops.append(
                DropColumnOp.from_column_and_tablename(
                    dbtable._tablename, metatable.columns[column_name]))

    def column(self, dbcolumn, metacolumn):
        self.notnulls(dbcolumn, metacolumn)
        self.types(dbcolumn, metacolumn)
        self.lengths(dbcolumn, metacolumn)
        self.defaults(dbcolumn, metacolumn)

    def types(self, dbcolumn, metacolumn):
        self.ops[-1].existing_type = metacolumn.type
        if dbcolumn.type != metacolumn.type:
            self.ops[-1].modify_type = dbcolumn.type

    def lengths(self, dbcolumn, metacolumn):
        self.ops[-1].existing_length = metacolumn.length
        if any(
            field.type == "string" for field in [dbcolumn, metacolumn]
        ) and dbcolumn.length != metacolumn.length:
            self.ops[-1].modify_length = dbcolumn.length

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
        for revision in reversed(
            list(self.scriptdir.walk_revisions("base", self.head))
        ):
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
        col for col in [_render_column(col) for col in table.columns.values()]
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
    elif column.type.startswith('reference'):
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
        "cname": op.column_name
    }


@renderers.dispatch_for(AlterColumnOp)
def _alter_column(op):
    indent = " " * 12
    text = "self.alter_column(%(tname)r, %(cname)r" % {
        'tname': op.table_name,
        'cname': op.column_name}

    if op.existing_type is not None:
        text += ",\n%sexisting_type=%r" % (indent, op.existing_type)
    if op.existing_length:
        text += ",\n%sexisting_length=%r" % (indent, op.existing_length)
    if op.modify_default is not DEFAULT_VALUE:
        text += ",\n%sdefault=%r" % (indent, op.modify_default)
    if op.modify_type is not None:
        text += ",\n%stype=%r" % (indent, op.modify_type)
    if op.modify_length is not None:
        text += ",\n%slength=%r" % (indent, op.modify_length)
    if op.modify_notnull is not None:
        text += ",\n%snotnull=%r" % (indent, op.modify_notnull)
    if op.modify_notnull is None and op.existing_notnull is not None:
        text += ",\n%sexisting_notnull=%r" % (indent, op.existing_notnull)
    if op.modify_default is DEFAULT_VALUE and op.existing_default:
        text += ",\n%sexisting_default=%s" % (indent, op.existing_default)

    text += ")"
    return text


@renderers.dispatch_for(CreateIndexOp)
def _add_index(op):
    kw_str = ""
    if op.kw:
        kw_str = ", %s" % ", ".join(
            ["%s=%r" % (key, val) for key, val in op.kw.items()])
    return "self.create_index(%(iname)r, %(tname)r, %(idata)s)" % {
        "tname": op.table_name,
        "iname": op.index_name,
        "idata": "%r, expressions=%r, unique=%s%s" % (
            op.fields, op.expressions, op.unique, kw_str)
    }


@renderers.dispatch_for(DropIndexOp)
def _drop_index(op):
    return "self.drop_index(%(iname)r, %(tname)r)" % {
        "tname": op.table_name,
        "iname": op.index_name
    }
