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

from __future__ import annotations

from collections import OrderedDict
from typing import Any, Dict, List, Optional

from ..._shortcuts import hashlib_sha1
from ...datastructures import OrderedSet
from ..objects import Rows, Table
from .base import Column, Database
from .helpers import Dispatcher, DEFAULT_VALUE
from .operations import (
    AddColumnOp,
    AlterColumnOp,
    CreateForeignKeyConstraintOp,
    CreateIndexOp,
    CreateTableOp,
    DropColumnOp,
    DropForeignKeyConstraintOp,
    DropIndexOp,
    DropTableOp,
    MigrationOp,
    OpContainer,
    Operation,
    UpgradeOps
)
from .scripts import ScriptDir


class MetaTable:
    def __init__(
        self,
        name: str,
        columns: List[Column] = [],
        primary_keys: List[str] = [],
        **kw: Any
    ):
        self.name = name
        self.columns = OrderedDict()
        for column in columns:
            self.columns[column.name] = column
        self.primary_keys = primary_keys
        self.indexes: Dict[str, MetaIndex] = {}
        self.foreign_keys: Dict[str, MetaForeignKey] = {}
        self.kw = kw

    @property
    def fields(self) -> List[str]:
        return list(self.columns)

    def __getitem__(self, name: str) -> Column:
        return self.columns[name]

    def __setitem__(self, name: str, value: Column):
        self.columns[name] = value

    def __delitem__(self, name: str):
        del self.columns[name]

    def __repr__(self) -> str:
        return "Table(%r, %s)" % (
            self.name,
            ", ".join(["%s" % column for column in self.columns.values()])
        )

    def insert(self, *args, **kwargs) -> Any:
        return None


class MetaIndex:
    def __init__(
        self,
        table_name: str,
        name: str,
        fields: List[str],
        expressions: List[str],
        unique: bool,
        **kw: Any
    ):
        self.table_name = table_name
        self.name = name
        self.fields = fields
        self.expressions = expressions
        self.unique = unique
        self.kw = kw

    @property
    def where(self) -> Optional[str]:
        return self.kw.get('where')

    def __repr__(self) -> str:
        opts = [('expressions', self.expressions), ('unique', self.unique)]
        for key, val in self.kw.items():
            opts.append((key, val))
        return "Index(%r, %r, %s)" % (
            self.name, self.fields,
            ", ".join(["%s=%r" % (opt[0], opt[1]) for opt in opts])
        )


class MetaForeignKey:
    def __init__(
        self,
        table_name: str,
        name: str,
        column_names: List[str],
        foreign_table_name: str,
        foreign_keys: List[str],
        on_delete: str,
        **kw
    ):
        self.table_name = table_name
        self.name = name
        self.column_names = column_names
        self.foreign_table_name = foreign_table_name
        self.foreign_keys = foreign_keys
        self.on_delete = on_delete
        self.kw = kw

    @property
    def _hash(self) -> str:
        return hashlib_sha1(
            f"{self.table_name}:{self.name}:{self.on_delete}:"
            f"{repr(sorted(self.column_names))}:{repr(sorted(self.foreign_keys))}"
        ).hexdigest()

    def __eq__(self, obj: Any) -> bool:
        if isinstance(obj, MetaForeignKey):
            return self._hash == obj._hash
        return False

    def __repr__(self) -> str:
        return "ForeignKey(%r, %r, %r, %r, %r, on_delete=%r)" % (
            self.name,
            self.table_name,
            self.foreign_table_name,
            self.column_names,
            self.foreign_keys,
            self.on_delete
        )


class MetaDataSet:
    def __init__(self, db: MetaData, *args, **kwargs):
        self.db = db
        self.args = args
        self.kwargs = kwargs

    def where(self, *args, **kwargs) -> MetaDataSet:
        return MetaDataSet(self.db, *args, **kwargs)

    def select(self, *args, **kwargs) -> Rows:
        return Rows(self.db)

    def update(self, *args, **kwargs) -> int:
        return 0

    def delete(self, *args, **kwargs) -> int:
        return 0


class MetaData:
    def __init__(self):
        self.tables: Dict[str, MetaTable] = {}

    def __getitem__(self, key):
        return self.tables[key]

    def __getattr__(self, name):
        return self.tables[name]

    def where(self, *args, **kwargs) -> MetaDataSet:
        return MetaDataSet(*args, **kwargs)

    def __call__(self, *args, **kwargs):
        return self.where(*args, **kwargs)

    def create_table(
        self,
        name: str,
        columns: List[Column],
        primary_keys: List[str],
        **kw: Any
    ):
        self.tables[name] = MetaTable(name, columns, primary_keys, **kw)

    def drop_table(self, name: str):
        del self.tables[name]

    def add_column(self, table: str, column: Column):
        self.tables[table][column.name] = column

    def drop_column(self, table: str, column: str):
        del self.tables[table][column]

    def change_column(self, table_name: str, column_name: str, changes: Dict[str, Any]):
        self.tables[table_name][column_name].update(**changes)

    def create_index(
        self,
        table_name: str,
        index_name: str,
        fields: List[str],
        expressions: List[str],
        unique: bool,
        **kw: Any
    ):
        self.tables[table_name].indexes[index_name] = MetaIndex(
            table_name, index_name, fields, expressions, unique, **kw
        )

    def drop_index(self, table_name: str, index_name: str):
        del self.tables[table_name].indexes[index_name]

    def create_foreign_key_constraint(
        self,
        table_name: str,
        constraint_name: str,
        column_names: List[str],
        foreign_table_name: str,
        foreign_keys: List[str],
        on_delete: str
    ):
        self.tables[table_name].foreign_keys[constraint_name] = MetaForeignKey(
            table_name,
            constraint_name,
            column_names,
            foreign_table_name,
            foreign_keys,
            on_delete
        )

    def drop_foreign_key_constraint(self, table_name: str, constraint_name: str):
        del self.tables[table_name].foreign_keys[constraint_name]


class Comparator:
    def __init__(self, db: Database, meta: MetaData):
        self.db = db
        self.meta = meta

    def make_ops(self) -> List[Operation]:
        self.ops: List[Operation] = []
        self.tables()
        return self.ops

    def _build_metatable(self, dbtable: Table):
        return MetaTable(
            dbtable._tablename,
            [
                Column.from_field(field) for field in list(dbtable)
            ],
            primary_keys=list(dbtable._primary_keys)
        )

    def _build_metaindex(self, dbtable: Table, index_name: str) -> MetaIndex:
        model = dbtable._model_
        dbindex = model._indexes_[index_name]
        kw = {}
        with self.db._adapter.index_expander():
            if 'where' in dbindex:
                kw['where'] = str(dbindex['where'])
            rv = MetaIndex(
                model.tablename,
                index_name,
                [field for field in dbindex['fields']],
                [str(expr) for expr in dbindex['expressions']],
                dbindex['unique'],
                **kw
            )
        return rv

    def _build_metafk(self, dbtable: Table, fk_name: str) -> MetaForeignKey:
        model = dbtable._model_
        dbfk = model._foreign_keys_[fk_name]
        return MetaForeignKey(
            model.tablename,
            fk_name,
            dbfk['fields_local'],
            dbfk['table'],
            dbfk['fields_foreign'],
            dbfk['on_delete']
        )

    def tables(self):
        db_table_names = OrderedSet([t._tablename for t in self.db])
        meta_table_names = OrderedSet(list(self.meta.tables))
        #: new tables
        for table_name in db_table_names.difference(meta_table_names):
            meta_table = self._build_metatable(self.db[table_name])
            self.ops.append(CreateTableOp.from_table(meta_table))
            self.indexes_and_uniques(self.db[table_name], meta_table)
            self.foreign_keys(self.db[table_name], meta_table)
        #: removed tables
        for table_name in meta_table_names.difference(db_table_names):
            #: remove table indexes too
            metatable = self.meta.tables[table_name]
            for idx in metatable.indexes.values():
                self.ops.append(DropIndexOp.from_index(idx))
            #: remove table
            self.ops.append(DropTableOp.from_table(self.meta.tables[table_name]))
        #: existing tables
        for table_name in meta_table_names.intersection(db_table_names):
            self.columns(self.db[table_name], self.meta.tables[table_name])
            self.table(self.db[table_name], self.meta.tables[table_name])

    def table(self, dbtable: Table, metatable: MetaTable):
        self.indexes_and_uniques(dbtable, metatable)
        self.foreign_keys(dbtable, metatable)

    def indexes_and_uniques(
        self,
        dbtable: Table,
        metatable: MetaTable,
        ops_stack: Optional[List[Operation]] = None
    ):
        ops = ops_stack if ops_stack is not None else self.ops
        db_index_names = OrderedSet(
            [idxname for idxname in dbtable._model_._indexes_.keys()]
        )
        meta_index_names = OrderedSet(list(metatable.indexes))
        #: removed indexes
        for index_name in meta_index_names.difference(db_index_names):
            ops.append(DropIndexOp.from_index(metatable.indexes[index_name]))
        #: new indexs
        for index_name in db_index_names.difference(meta_index_names):
            ops.append(
                CreateIndexOp.from_index(
                    self._build_metaindex(dbtable, index_name)
                )
            )
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

    def foreign_keys(
        self,
        dbtable: Table,
        metatable: MetaTable,
        ops_stack: Optional[List[Operation]] = None
    ):
        ops = ops_stack if ops_stack is not None else self.ops
        db_fk_names = OrderedSet(
            [fkname for fkname in dbtable._model_._foreign_keys_.keys()]
        )
        meta_fk_names = OrderedSet(list(metatable.foreign_keys))
        #: removed fks
        for fk_name in meta_fk_names.difference(db_fk_names):
            ops.append(
                DropForeignKeyConstraintOp.from_foreign_key(
                    metatable.foreign_keys[fk_name]
                )
            )
        #: new fks
        for fk_name in db_fk_names.difference(meta_fk_names):
            ops.append(
                CreateForeignKeyConstraintOp.from_foreign_key(
                    self._build_metafk(dbtable, fk_name)
                )
            )
        #: existing fks
        for fk_name in meta_fk_names.intersection(db_fk_names):
            metafk = metatable.foreign_keys[fk_name]
            dbfk = self._build_metafk(dbtable, fk_name)
            if metafk != dbfk:
                ops.append(DropForeignKeyConstraintOp.from_foreign_key(metafk))
                ops.append(CreateForeignKeyConstraintOp.from_foreign_key(dbfk))

    def columns(self, dbtable: Table, metatable: MetaTable):
        db_column_names = OrderedSet([fname for fname in dbtable.fields])
        meta_column_names = OrderedSet(metatable.fields)
        #: new columns
        for column_name in db_column_names.difference(meta_column_names):
            self.ops.append(AddColumnOp.from_column_and_tablename(
                dbtable._tablename, Column.from_field(dbtable[column_name])
            ))
        #: existing columns
        for column_name in meta_column_names.intersection(db_column_names):
            self.ops.append(AlterColumnOp(dbtable._tablename, column_name))
            self.column(
                Column.from_field(dbtable[column_name]),
                metatable.columns[column_name]
            )
            if not self.ops[-1].has_changes():
                self.ops.pop()
        #: removed columns
        for column_name in meta_column_names.difference(db_column_names):
            self.ops.append(
                DropColumnOp.from_column_and_tablename(
                    dbtable._tablename, metatable.columns[column_name]
                )
            )

    def column(self, dbcolumn: Column, metacolumn: Column):
        self.notnulls(dbcolumn, metacolumn)
        self.types(dbcolumn, metacolumn)
        self.lengths(dbcolumn, metacolumn)
        self.defaults(dbcolumn, metacolumn)

    def types(self, dbcolumn: Column, metacolumn: Column):
        self.ops[-1].existing_type = metacolumn.type
        if dbcolumn.type != metacolumn.type:
            self.ops[-1].modify_type = dbcolumn.type
        if dbcolumn.geometry_type and metacolumn.geometry_type:
            for key in ("geometry_type", "srid", "dimension"):
                self.ops[-1].kw[f"existing_{key}"] = metacolumn[key]
                if dbcolumn[key] != metacolumn[key]:
                    self.ops[-1].kw[f"modify_{key}"] = dbcolumn[key]

    def lengths(self, dbcolumn: Column, metacolumn: Column):
        self.ops[-1].existing_length = metacolumn.length
        if any(
            field.type == "string" for field in [dbcolumn, metacolumn]
        ) and dbcolumn.length != metacolumn.length:
            self.ops[-1].modify_length = dbcolumn.length

    def notnulls(self, dbcolumn: Column, metacolumn: Column):
        self.ops[-1].existing_notnull = metacolumn.notnull
        if dbcolumn.notnull != metacolumn.notnull:
            self.ops[-1].modify_notnull = dbcolumn.notnull

    def defaults(self, dbcolumn: Column, metacolumn: Column):
        self.ops[-1].existing_default = metacolumn.default
        if dbcolumn.default != metacolumn.default:
            self.ops[-1].modify_default = dbcolumn.default

    @classmethod
    def compare(cls, db: Database, meta: MetaData) -> UpgradeOps:
        ops = cls(db, meta).make_ops()
        return UpgradeOps(ops)


class Generator:
    def __init__(self, db: Database, scriptdir: ScriptDir, head: str):
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
                None, self.meta, is_meta=True
            )
            if migration.skip_on_compare:
                continue
            migration.up()

    def generate(self) -> UpgradeOps:
        return Comparator.compare(self.db, self.meta)

    @classmethod
    def generate_from(
        cls,
        dal: Database,
        scriptdir: ScriptDir,
        head: str
    ) -> UpgradeOps:
        return cls(dal, scriptdir, head).generate()


class Renderer:
    def render_op(self, op: Operation) -> str:
        op_renderer = renderers.dispatch(op)
        return op_renderer(op)

    def render_opcontainer(self, op_container: OpContainer) -> List[str]:
        rv = []
        if not op_container.ops:
            rv.append("pass")
        else:
            for op in op_container.ops:
                rv.append(self.render_op(op))
        return rv

    @classmethod
    def render_migration(cls, migration_op: MigrationOp):
        r = cls()
        return (
            r.render_opcontainer(migration_op.upgrade_ops),
            r.render_opcontainer(migration_op.downgrade_ops)
        )


renderers = Dispatcher()


@renderers.dispatch_for(CreateTableOp)
def _add_table(op: CreateTableOp) -> str:
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

    text = (
        "self.create_table(\n" + indent + "%(tablename)r,\n" + indent + "%(args)s,\n" +
        indent + "primary_keys=%(primary_keys)r"
    ) % {
        'tablename': op.table_name,
        'args': args,
        'primary_keys': table.primary_keys
    }
    for k in sorted(op.kw):
        text += ",\n" + indent + "%s=%r" % (k.replace(" ", "_"), op.kw[k])
    text += ")"
    return text


@renderers.dispatch_for(DropTableOp)
def _drop_table(op: DropTableOp) -> str:
    text = "self.drop_table(%(tname)r" % {
        "tname": op.table_name
    }
    text += ")"
    return text


def _render_column(column: Column) -> str:
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
    elif column.type.startswith("geo"):
        for key in ("geometry_type", "srid", "dimension"):
            if column[key] is not None:
                opts.append((key, column[key]))

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
def _add_column(op: AddColumnOp) -> str:
    return "self.add_column(%(tname)r, %(column)s)" % {
        "tname": op.table_name,
        "column": _render_column(op.column)
    }


@renderers.dispatch_for(DropColumnOp)
def _drop_column(op: DropTableOp) -> str:
    return "self.drop_column(%(tname)r, %(cname)r)" % {
        "tname": op.table_name,
        "cname": op.column_name
    }


@renderers.dispatch_for(AlterColumnOp)
def _alter_column(op: AlterColumnOp) -> str:
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
    for key, val in op.kw.items():
        if key.startswith("existing_") or key.startswith("modify_"):
            text += ",\n%s%s=%r" % (indent, key, val)

    text += ")"
    return text


@renderers.dispatch_for(CreateIndexOp)
def _add_index(op: CreateIndexOp) -> str:
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
def _drop_index(op: DropIndexOp) -> str:
    return "self.drop_index(%(iname)r, %(tname)r)" % {
        "tname": op.table_name,
        "iname": op.index_name
    }


@renderers.dispatch_for(CreateForeignKeyConstraintOp)
def _add_fk_constraint(op: CreateForeignKeyConstraintOp) -> str:
    kw_str = ""
    if op.kw:
        kw_str = ", %s" % ", ".join(
            ["%s=%r" % (key, val) for key, val in op.kw.items()]
        )
    return "self.create_foreign_key(%s%s)" % (
        "%r, %r, %r, %r, %r, on_delete=%r" % (
            op.constraint_name,
            op.table_name,
            op.foreign_table_name,
            op.column_names,
            op.foreign_keys,
            op.on_delete
        ),
        kw_str
    )


@renderers.dispatch_for(DropForeignKeyConstraintOp)
def _drop_fk_constraint(op: DropForeignKeyConstraintOp) -> str:
    return "self.drop_foreign_key(%(cname)r, %(tname)r)" % {
        "tname": op.table_name,
        "cname": op.constraint_name
    }
