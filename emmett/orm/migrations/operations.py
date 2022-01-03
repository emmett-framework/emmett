# -*- coding: utf-8 -*-
"""
    emmett.orm.migrations.operations
    --------------------------------

    Provides operations handlers for migrations.

    :copyright: 2014 Giovanni Barillari

    Based on the code of Alembic (https://bitbucket.org/zzzeek/alembic)
    :copyright: (c) 2009-2015 by Michael Bayer

    :license: BSD-3-Clause
"""

from __future__ import annotations

import re

from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from .base import Migration, Column
from .helpers import DEFAULT_VALUE

if TYPE_CHECKING:
    from .engine import MetaEngine
    from .generation import MetaTable, MetaIndex, MetaForeignKey


class Operation:
    def _env_load_(self, engine: MetaEngine):
        self.engine = engine

    def reverse(self) -> Operation:
        raise NotImplementedError

    def run(self):
        pass


class OpContainer(Operation):
    #: represent a sequence of operations
    def __init__(self, ops: List[Operation] = []):
        self.ops = ops

    def is_empty(self) -> bool:
        return not self.ops

    def as_diffs(self):
        return list(OpContainer._ops_as_diffs(self))

    @classmethod
    def _ops_as_diffs(cls, migrations):
        for op in migrations.ops:
            if hasattr(op, 'ops'):
                for sub_op in cls._ops_as_diffs(op):
                    yield sub_op
            else:
                yield op.to_diff_tuple()


class ModifyTableOps(OpContainer):
    #: a sequence of operations that all apply to a single Table
    def __init__(self, table_name: str, ops: List[Operation]):
        super().__init__(ops)
        self.table_name = table_name

    def reverse(self) -> ModifyTableOps:
        return ModifyTableOps(
            self.table_name,
            ops=list(reversed([op.reverse() for op in self.ops]))
        )


class UpgradeOps(OpContainer):
    #: contains a sequence of operations that would apply during upgrade
    def __init__(self, ops: List[Operation] = [], upgrade_token: str = "upgrades"):
        super().__init__(ops=ops)
        self.upgrade_token = upgrade_token

    def reverse(self) -> DowngradeOps:
        return DowngradeOps(
            ops=list(reversed([op.reverse() for op in self.ops]))
        )


class DowngradeOps(OpContainer):
    #: contains a sequence of operations that would apply during downgrade
    def __init__(self, ops: List[Operation] = [], downgrade_token: str = "downgrades"):
        super().__init__(ops=ops)
        self.downgrade_token = downgrade_token

    def reverse(self):
        return UpgradeOps(
            ops=list(reversed([op.reverse() for op in self.ops]))
        )


class MigrationOp(Operation):
    def __init__(
        self,
        rev_id: str,
        upgrade_ops: UpgradeOps,
        downgrade_ops: DowngradeOps,
        message: Optional[str] = None,
        head: Optional[str] = None,
        splice: Any = None
    ):
        self.rev_id = rev_id
        self.message = message
        self.head = head
        self.splice = splice
        self.upgrade_ops = upgrade_ops
        self.downgrade_ops = downgrade_ops


@Migration.register_operation("create_table")
class CreateTableOp(Operation):
    def __init__(
        self,
        table_name: str,
        columns: List[Column],
        primary_keys: List[str] = [],
        _orig_table: Optional[MetaTable] = None,
        **kw: Any
    ):
        self.table_name = table_name
        self.columns = columns
        self.primary_keys = primary_keys
        self.kw = kw
        self._orig_table = _orig_table

    def reverse(self) -> DropTableOp:
        return DropTableOp.from_table(self.to_table())

    def to_diff_tuple(self) -> Tuple[str, MetaTable]:
        return ("add_table", self.to_table())

    @classmethod
    def from_table(cls, table: MetaTable) -> CreateTableOp:
        return cls(
            table.name,
            [table[colname] for colname in table.fields],
            list(table.primary_keys),
            _orig_table=table
        )

    def to_table(self, migration_context: Any = None) -> MetaTable:
        if self._orig_table is not None:
            return self._orig_table
        from .generation import MetaTable
        return MetaTable(
            self.table_name,
            self.columns,
            self.primary_keys,
            **self.kw
        )

    @classmethod
    def create_table(
        cls,
        table_name: str,
        *columns: Column,
        **kw: Any
    ) -> CreateTableOp:
        return cls(table_name, columns, **kw)

    def run(self):
        self.engine.create_table(
            self.table_name, self.columns, self.primary_keys, **self.kw
        )


@Migration.register_operation("drop_table")
class DropTableOp(Operation):
    def __init__(
        self,
        table_name: str,
        table_kw: Optional[Dict[str, Any]] = None,
        _orig_table: Optional[MetaTable] = None
    ):
        self.table_name = table_name
        self.table_kw = table_kw or {}
        self._orig_table = _orig_table

    def to_diff_tuple(self) -> Tuple[str, MetaTable]:
        return ("remove_table", self.to_table())

    def reverse(self) -> CreateTableOp:
        if self._orig_table is None:
            raise ValueError(
                "operation is not reversible; original table is not present"
            )
        return CreateTableOp.from_table(self._orig_table)

    @classmethod
    def from_table(cls, table: MetaTable) -> DropTableOp:
        return cls(table.name, _orig_table=table)

    def to_table(self) -> MetaTable:
        if self._orig_table is not None:
            return self._orig_table
        from .generation import MetaTable
        return MetaTable(
            self.table_name,
            **self.table_kw
        )

    @classmethod
    def drop_table(cls, table_name: str, **kw: Any) -> DropTableOp:
        return cls(table_name, table_kw=kw)

    def run(self):
        self.engine.drop_table(self.table_name)


class AlterTableOp(Operation):
    def __init__(self, table_name: str):
        self.table_name = table_name


@Migration.register_operation("rename_table")
class RenameTableOp(AlterTableOp):
    def __init__(self, old_table_name: str, new_table_name: str):
        super().__init__(old_table_name)
        self.new_table_name = new_table_name

    @classmethod
    def rename_table(cls, old_table_name: str, new_table_name: str) -> RenameTableOp:
        return cls(old_table_name, new_table_name)

    def run(self):
        raise NotImplementedError('Table renaming is currently not supported.')


@Migration.register_operation("add_column")
class AddColumnOp(AlterTableOp):
    def __init__(self, table_name: str, column: Column):
        super().__init__(table_name)
        self.column = column

    def reverse(self) -> DropColumnOp:
        return DropColumnOp.from_column_and_tablename(self.table_name, self.column)

    def to_diff_tuple(self) -> Tuple[str, str, Column]:
        return ("add_column", self.table_name, self.column)

    def to_column(self) -> Column:
        return self.column

    @classmethod
    def from_column_and_tablename(cls, tname: str, col: Column) -> AddColumnOp:
        return cls(tname, col)

    @classmethod
    def add_column(cls, table_name: str, column: Column) -> AddColumnOp:
        return cls(table_name, column)

    def run(self):
        self.engine.add_column(self.table_name, self.column)


@Migration.register_operation("drop_column")
class DropColumnOp(AlterTableOp):
    def __init__(
        self,
        table_name: str,
        column_name: str,
        _orig_column: Optional[Column] = None,
        **kw: Any
    ):
        super().__init__(table_name)
        self.column_name = column_name
        self.kw = kw
        self._orig_column = _orig_column

    def to_diff_tuple(self) -> Tuple[str, str, Column]:
        return ("remove_column", self.table_name, self.to_column())

    def reverse(self) -> AddColumnOp:
        if self._orig_column is None:
            raise ValueError(
                "operation is not reversible; original column is not present"
            )

        return AddColumnOp.from_column_and_tablename(
            self.table_name, self._orig_column
        )

    @classmethod
    def from_column_and_tablename(cls, tname: str, col: Column) -> DropColumnOp:
        return cls(tname, col.name, _orig_column=col)

    def to_column(self) -> Column:
        if self._orig_column is not None:
            return self._orig_column
        return Column(self.column_name, **self.kw)

    @classmethod
    def drop_column(cls, table_name: str, column_name: str, **kw: Any) -> DropColumnOp:
        return cls(table_name, column_name, **kw)

    def run(self):
        self.engine.drop_column(self.table_name, self.column_name)


@Migration.register_operation("alter_column")
class AlterColumnOp(AlterTableOp):
    def __init__(
        self,
        table_name: str,
        column_name: str,
        existing_type: Optional[str] = None,
        existing_length: Optional[int] = None,
        existing_default: Any = None,
        existing_notnull: Optional[bool] = None,
        modify_notnull: Optional[bool] = None,
        modify_default: Any = DEFAULT_VALUE,
        modify_name: Optional[str] = None,
        modify_type: Optional[str] = None,
        modify_length: Optional[int] = None,
        **kw: Any
    ):
        super().__init__(table_name)
        self.column_name = column_name
        self.existing_type = existing_type
        self.existing_length = existing_length
        self.existing_default = existing_default
        self.existing_notnull = existing_notnull
        self.modify_notnull = modify_notnull
        self.modify_default = modify_default
        self.modify_name = modify_name
        self.modify_type = modify_type
        self.modify_length = modify_length
        self.kw = kw

    def to_diff_tuple(self) -> List[Tuple[str, str, str, Dict[str, Any], Any, Any]]:
        col_diff = []
        tname, cname = self.table_name, self.column_name

        if self.modify_type is not None:
            col_diff.append(
                (
                    "modify_type",
                    tname,
                    cname,
                    {
                        "existing_length": self.existing_length,
                        "existing_notnull": self.existing_notnull,
                        "existing_default": self.existing_default,
                        **{
                            nkey: nval for nkey, nval in self.kw.items()
                            if nkey.startswith('existing_')
                        }
                    },
                    self.existing_type,
                    self.modify_type
                )
            )

        if self.modify_length is not None:
            col_diff.append(
                (
                    "modify_length",
                    tname,
                    cname,
                    {
                        "existing_type": self.existing_type,
                        "existing_notnull": self.existing_notnull,
                        "existing_default": self.existing_default
                    },
                    self.existing_length,
                    self.modify_length
                )
            )

        if self.modify_notnull is not None:
            col_diff.append(
                (
                    "modify_notnull",
                    tname,
                    cname,
                    {
                        "existing_type": self.existing_type,
                        "existing_default": self.existing_default
                    },
                    self.existing_notnull,
                    self.modify_notnull
                )
            )

        if self.modify_default is not DEFAULT_VALUE:
            col_diff.append(
                (
                    "modify_default",
                    tname,
                    cname,
                    {
                        "existing_notnull": self.existing_notnull,
                        "existing_type": self.existing_type
                    },
                    self.existing_default,
                    self.modify_default
                )
            )

        for key, val in self.kw.items():
            if key.startswith("modify_"):
                attr = key.split("modify_")[-1]
                col_diff.append(
                    (
                        key,
                        tname,
                        cname,
                        {
                            "existing_type": self.existing_type,
                            **{
                                nkey: nval for nkey, nval in self.kw.items()
                                if nkey.startswith('existing_')
                            }
                        },
                        self.kw.get(f"existing_{attr}"),
                        val
                    )
                )

        return col_diff

    def has_changes(self) -> bool:
        hc = (
            self.modify_notnull is not None or
            self.modify_default is not DEFAULT_VALUE or
            self.modify_type is not None or
            self.modify_length is not None
        )
        if hc:
            return True
        for kw in self.kw:
            if kw.startswith('modify_'):
                return True
        return False

    def reverse(self) -> AlterColumnOp:
        kw = self.kw.copy()
        kw['existing_type'] = self.existing_type
        kw['existing_length'] = self.existing_length
        kw['existing_notnull'] = self.existing_notnull
        kw['existing_default'] = self.existing_default
        if self.modify_type is not None:
            kw['modify_type'] = self.modify_type
        if self.modify_length is not None:
            kw['modify_length'] = self.modify_length
        if self.modify_notnull is not None:
            kw['modify_notnull'] = self.modify_notnull
        if self.modify_default is not DEFAULT_VALUE:
            kw['modify_default'] = self.modify_default

        all_keys = set(m.group(1) for m in [
            re.match(r'^(?:existing_|modify_)(.+)$', k)
            for k in kw
        ] if m)

        for k in all_keys:
            if 'modify_%s' % k in kw:
                swap = kw['existing_%s' % k]
                kw['existing_%s' % k] = kw['modify_%s' % k]
                kw['modify_%s' % k] = swap

        return self.__class__(
            self.table_name, self.column_name, **kw
        )

    @classmethod
    def alter_column(
        cls,
        table_name: str,
        column_name: str,
        notnull: Optional[bool] = None,
        default: Any = DEFAULT_VALUE,
        new_column_name: Optional[str] = None,
        type: Optional[str] = None,
        length: Optional[int] = None,
        existing_type: Optional[str] = None,
        existing_length: Optional[int] = None,
        existing_default: Any = None,
        existing_notnull: Optional[bool] = None,
        **kw: Any
    ) -> AlterColumnOp:
        return cls(
            table_name,
            column_name,
            existing_type=existing_type,
            existing_length=existing_length,
            existing_default=existing_default,
            existing_notnull=existing_notnull,
            modify_name=new_column_name,
            modify_type=type,
            modify_length=length,
            modify_default=default,
            modify_notnull=notnull,
            **kw
        )

    def run(self):
        self.engine.alter_column(
            self.table_name, self.column_name, self.to_diff_tuple()
        )


@Migration.register_operation("create_index")
class CreateIndexOp(Operation):
    def __init__(
        self,
        index_name: str,
        table_name: str,
        fields: List[str] = [],
        expressions: List[str] = [],
        unique: bool = False,
        _orig_index: Optional[MetaIndex] = None,
        **kw: Any
    ):
        self.index_name = index_name
        self.table_name = table_name
        self.fields = fields
        self.expressions = expressions
        self.unique = unique
        self.kw = kw
        self._orig_index = _orig_index

    def reverse(self) -> DropIndexOp:
        return DropIndexOp.from_index(self.to_index())

    def to_diff_tuple(self) -> Tuple[str, MetaIndex]:
        return ("create_index", self.to_index())

    @classmethod
    def from_index(cls, index: MetaIndex) -> CreateIndexOp:
        return cls(
            index.name, index.table_name, index.fields, index.expressions,
            index.unique, _orig_index=index, **index.kw
        )

    def to_index(self) -> MetaIndex:
        if self._orig_index is not None:
            return self._orig_index
        from .generation import MetaIndex
        return MetaIndex(
            self.table_name,
            self.index_name,
            self.fields,
            self.expressions,
            self.unique,
            **self.kw
        )

    @classmethod
    def create_index(
        cls,
        index_name: str,
        table_name: str,
        fields: List[str] = [],
        expressions: List[str] = [],
        unique: bool = False,
        **kw: Any
    ) -> CreateIndexOp:
        return cls(index_name, table_name, fields, expressions, unique, **kw)

    def run(self):
        self.engine.create_index(
            self.index_name,
            self.table_name,
            self.fields,
            self.expressions,
            self.unique,
            **self.kw
        )


@Migration.register_operation("drop_index")
class DropIndexOp(Operation):
    def __init__(
        self,
        index_name: str,
        table_name: Optional[str] = None,
        _orig_index: Optional[MetaIndex] = None
    ):
        self.index_name = index_name
        self.table_name = table_name
        self._orig_index = _orig_index

    def to_diff_tuple(self) -> Tuple[str, MetaIndex]:
        return ("remove_index", self.to_index())

    def reverse(self) -> CreateIndexOp:
        if self._orig_index is None:
            raise ValueError(
                "operation is not reversible; original index is not present"
            )
        return CreateIndexOp.from_index(self._orig_index)

    @classmethod
    def from_index(cls, index: MetaIndex) -> DropIndexOp:
        return cls(index.name, index.table_name, index)

    def to_index(self) -> MetaIndex:
        if self._orig_index is not None:
            return self._orig_index
        from .generation import MetaIndex
        return MetaIndex(self.table_name, self.index_name, [], [], False)

    @classmethod
    def drop_index(cls, index_name: str, table_name: str) -> DropIndexOp:
        return cls(index_name, table_name)

    def run(self):
        self.engine.drop_index(self.index_name, self.table_name)


@Migration.register_operation("create_foreign_key")
class CreateForeignKeyConstraintOp(AlterTableOp):
    def __init__(
        self,
        name: str,
        table_name: str,
        foreign_table_name: str,
        column_names: List[str],
        foreign_keys: List[str],
        on_delete: str,
        _orig_fk: Optional[MetaForeignKey] = None,
        **kw: Any
    ):
        super().__init__(table_name)
        self.constraint_name = name
        self.foreign_table_name = foreign_table_name
        self.column_names = column_names
        self.foreign_keys = foreign_keys
        self.on_delete = on_delete
        self.kw = kw
        self._orig_fk = _orig_fk
        if len(self.column_names) != len(self.foreign_keys):
            raise SyntaxError("local and foreign columns number should match")

    def reverse(self) -> DropForeignKeyConstraintOp:
        return DropForeignKeyConstraintOp.from_foreign_key(self.to_foreign_key())

    def to_diff_tuple(self) -> Tuple[str, MetaForeignKey]:
        return ("create_fk_constraint", self.to_foreign_key())

    @classmethod
    def from_foreign_key(
        cls,
        foreign_key: MetaForeignKey
    ) -> CreateForeignKeyConstraintOp:
        return cls(
            foreign_key.name,
            foreign_key.table_name,
            foreign_key.foreign_table_name,
            foreign_key.column_names,
            foreign_key.foreign_keys,
            foreign_key.on_delete,
            _orig_fk=foreign_key
        )

    def to_foreign_key(self) -> MetaForeignKey:
        if self._orig_fk is not None:
            return self._orig_fk

        from .generation import MetaForeignKey
        return MetaForeignKey(
            self.table_name,
            self.constraint_name,
            self.column_names,
            self.foreign_table_name,
            self.foreign_keys,
            self.on_delete
        )

    @classmethod
    def create_foreign_key(
        cls,
        name: str,
        table_name: str,
        foreign_table_name: str,
        column_names: List[str],
        foreign_keys: List[str],
        on_delete: str
    ) -> CreateForeignKeyConstraintOp:
        return cls(
            name=name,
            table_name=table_name,
            foreign_table_name=foreign_table_name,
            column_names=column_names,
            foreign_keys=foreign_keys,
            on_delete=on_delete
        )

    def run(self):
        self.engine.create_foreign_key_constraint(
            self.constraint_name,
            self.table_name,
            self.column_names,
            self.foreign_table_name,
            self.foreign_keys,
            self.on_delete
        )


@Migration.register_operation("drop_foreign_key")
class DropForeignKeyConstraintOp(AlterTableOp):
    def __init__(
        self,
        name: str,
        table_name: str,
        _orig_fk: Optional[MetaForeignKey] = None,
        **kw: Any
    ):
        super().__init__(table_name)
        self.constraint_name = name
        self.kw = kw
        self._orig_fk = _orig_fk

    def reverse(self) -> CreateForeignKeyConstraintOp:
        if self._orig_fk is None:
            raise ValueError(
                "operation is not reversible; original constraint is not present"
            )
        return CreateForeignKeyConstraintOp.from_foreign_key(self._orig_fk)

    def to_diff_tuple(self) -> Tuple[str, MetaForeignKey]:
        return ("drop_fk_constraint", self.to_foreign_key())

    @classmethod
    def from_foreign_key(
        cls,
        foreign_key: MetaForeignKey
    ) -> DropForeignKeyConstraintOp:
        return cls(
            foreign_key.name,
            foreign_key.table_name,
            _orig_fk=foreign_key
        )

    def to_foreign_key(self):
        if self._orig_fk is not None:
            return self._orig_fk

        from .generation import MetaForeignKey
        return MetaForeignKey(self.table_name, self.constraint_name, [], '', [], '')

    @classmethod
    def drop_foreign_key(
        cls,
        name: str,
        table_name: str
    ) -> DropForeignKeyConstraintOp:
        return DropForeignKeyConstraintOp(name, table_name)

    def run(self):
        self.engine.drop_foreign_key_constraint(self.constraint_name, self.table_name)


# @Migration.register_operation("execute")
# class ExecuteSQLOp(Operation):
#     def __init__(self, sqltext):
#         self.sqltext = sqltext

#     def run(self):
#         pass
