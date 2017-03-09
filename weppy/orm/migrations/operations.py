# -*- coding: utf-8 -*-
"""
    weppy.orm.migrations.operations
    -------------------------------

    Provides operations handlers for migrations.

    :copyright: (c) 2014-2017 by Giovanni Barillari

    Based on the code of Alembic (https://bitbucket.org/zzzeek/alembic)
    :copyright: (c) 2009-2015 by Michael Bayer

    :license: BSD, see LICENSE for more details.
"""

import re
from .base import Migration, Column
from .helpers import DEFAULT_VALUE


class Operation(object):
    def _env_load_(self, engine):
        self.engine = engine

    def run(self):
        pass


class OpContainer(Operation):
    #: represent a sequence of operations
    def __init__(self, ops=()):
        self.ops = ops

    def is_empty(self):
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
    def __init__(self, table_name, ops):
        super(ModifyTableOps, self).__init__(ops)
        self.table_name = table_name

    def reverse(self):
        return ModifyTableOps(
            self.table_name,
            ops=list(reversed(
                [op.reverse() for op in self.ops]
            ))
        )


class UpgradeOps(OpContainer):
    #: contains a sequence of operations that would apply during upgrade
    def __init__(self, ops=(), upgrade_token="upgrades"):
        super(UpgradeOps, self).__init__(ops=ops)
        self.upgrade_token = upgrade_token

    def reverse(self):
        return DowngradeOps(
            ops=list(reversed(
                [op.reverse() for op in self.ops]
            ))
        )


class DowngradeOps(OpContainer):
    #: contains a sequence of operations that would apply during downgrade
    def __init__(self, ops=(), downgrade_token="downgrades"):
        super(DowngradeOps, self).__init__(ops=ops)
        self.downgrade_token = downgrade_token

    def reverse(self):
        return UpgradeOps(
            ops=list(reversed(
                [op.reverse() for op in self.ops]
            ))
        )


class MigrationOp(Operation):
    def __init__(self, rev_id, upgrade_ops, downgrade_ops, message=None,
                 head=None, splice=None):
        self.rev_id = rev_id
        self.message = message
        self.head = head
        self.splice = splice
        self.upgrade_ops = upgrade_ops
        self.downgrade_ops = downgrade_ops


@Migration.register_operation("create_table")
class CreateTableOp(Operation):
    def __init__(self, table_name, columns, _orig_table=None, **kw):
        self.table_name = table_name
        self.columns = columns
        self.kw = kw
        self._orig_table = _orig_table

    def reverse(self):
        return DropTableOp.from_table(self.to_table())

    def to_diff_tuple(self):
        return ("add_table", self.to_table())

    @classmethod
    def from_table(cls, table):
        return cls(
            table.name,
            [table[colname] for colname in table.fields],
            _orig_table=table
        )

    def to_table(self, migration_context=None):
        if self._orig_table is not None:
            return self._orig_table
        from .generation import MetaTable
        return MetaTable(
            self.table_name, self.columns, **self.kw
        )

    @classmethod
    def create_table(cls, table_name, *columns, **kw):
        return cls(table_name, columns, **kw)

    def run(self):
        self.engine.create_table(self.table_name, self.columns, **self.kw)


@Migration.register_operation("drop_table")
class DropTableOp(Operation):
    def __init__(self, table_name, table_kw=None, _orig_table=None):
        self.table_name = table_name
        self.table_kw = table_kw or {}
        self._orig_table = _orig_table

    def to_diff_tuple(self):
        return ("remove_table", self.to_table())

    def reverse(self):
        if self._orig_table is None:
            raise ValueError(
                "operation is not reversible; "
                "original table is not present")
        return CreateTableOp.from_table(self._orig_table)

    @classmethod
    def from_table(cls, table):
        return cls(table.name, _orig_table=table)

    def to_table(self):
        if self._orig_table is not None:
            return self._orig_table
        from .generation import MetaTable
        return MetaTable(
            self.table_name,
            **self.table_kw)

    @classmethod
    def drop_table(cls, table_name, **kw):
        return cls(table_name, table_kw=kw)

    def run(self):
        self.engine.drop_table(self.table_name)


class AlterTableOp(Operation):
    def __init__(self, table_name):
        self.table_name = table_name


@Migration.register_operation("rename_table")
class RenameTableOp(AlterTableOp):
    def __init__(self, old_table_name, new_table_name):
        super(RenameTableOp, self).__init__(old_table_name)
        self.new_table_name = new_table_name

    @classmethod
    def rename_table(cls, old_table_name, new_table_name):
        return cls(old_table_name, new_table_name)

    def run(self):
        raise NotImplementedError(
            'Table renaming is currently not supported.'
        )


@Migration.register_operation("add_column")
class AddColumnOp(AlterTableOp):
    def __init__(self, table_name, column):
        super(AddColumnOp, self).__init__(table_name)
        self.column = column

    def reverse(self):
        return DropColumnOp.from_column_and_tablename(
            self.table_name, self.column)

    def to_diff_tuple(self):
        return ("add_column", self.table_name, self.column)

    def to_column(self):
        return self.column

    @classmethod
    def from_column_and_tablename(cls, tname, col):
        return cls(tname, col)

    @classmethod
    def add_column(cls, table_name, column):
        return cls(table_name, column)

    def run(self):
        self.engine.add_column(self.table_name, self.column)


@Migration.register_operation("drop_column")
class DropColumnOp(AlterTableOp):
    def __init__(self, table_name, column_name, _orig_column=None, **kw):
        super(DropColumnOp, self).__init__(table_name)
        self.column_name = column_name
        self.kw = kw
        self._orig_column = _orig_column

    def to_diff_tuple(self):
        return ("remove_column", self.table_name, self.to_column())

    def reverse(self):
        if self._orig_column is None:
            raise ValueError(
                "operation is not reversible; "
                "original column is not present")

        return AddColumnOp.from_column_and_tablename(
            self.table_name, self._orig_column)

    @classmethod
    def from_column_and_tablename(cls, tname, col):
        return cls(tname, col.name, _orig_column=col)

    def to_column(self):
        if self._orig_column is not None:
            return self._orig_column
        return Column(self.column_name, **self.kw)

    @classmethod
    def drop_column(cls, table_name, column_name, **kw):
        return cls(table_name, column_name, **kw)

    def run(self):
        self.engine.drop_column(self.table_name, self.column_name)


@Migration.register_operation("alter_column")
class AlterColumnOp(AlterTableOp):
    def __init__(
            self, table_name, column_name,
            existing_type=None,
            existing_default=None,
            existing_notnull=None,
            modify_notnull=None,
            modify_default=DEFAULT_VALUE,
            modify_name=None,
            modify_type=None,
            **kw

    ):
        super(AlterColumnOp, self).__init__(table_name)
        self.column_name = column_name
        self.existing_type = existing_type
        self.existing_default = existing_default
        self.existing_notnull = existing_notnull
        self.modify_notnull = modify_notnull
        self.modify_default = modify_default
        self.modify_name = modify_name
        self.modify_type = modify_type
        self.kw = kw

    def to_diff_tuple(self):
        col_diff = []
        tname, cname = self.table_name, self.column_name

        if self.modify_type is not None:
            col_diff.append(
                (
                    "modify_type", tname, cname, {
                        "existing_notnull": self.existing_notnull,
                        "existing_default": self.existing_default},
                    self.existing_type,
                    self.modify_type
                )
            )

        if self.modify_notnull is not None:
            col_diff.append(
                (
                    "modify_notnull", tname, cname, {
                        "existing_type": self.existing_type,
                        "existing_default": self.existing_default},
                    self.existing_notnull,
                    self.modify_notnull
                )
            )

        if self.modify_default is not DEFAULT_VALUE:
            col_diff.append(
                (
                    "modify_default", tname, cname, {
                        "existing_notnull": self.existing_notnull,
                        "existing_type": self.existing_type},
                    self.existing_default,
                    self.modify_default
                )
            )

        return col_diff

    def has_changes(self):
        hc = self.modify_notnull is not None or \
            self.modify_default is not DEFAULT_VALUE or \
            self.modify_type is not None
        if hc:
            return True
        for kw in self.kw:
            if kw.startswith('modify_'):
                return True
        else:
            return False

    def reverse(self):
        kw = self.kw.copy()
        kw['existing_type'] = self.existing_type
        kw['existing_notnull'] = self.existing_notnull
        kw['existing_default'] = self.existing_default
        if self.modify_type is not None:
            kw['modify_type'] = self.modify_type
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
        cls, table_name, column_name,
        notnull=None,
        default=DEFAULT_VALUE,
        new_column_name=None,
        type=None,
        existing_type=None,
        existing_default=None,
        existing_notnull=None,
        **kw
    ):
        return cls(
            table_name, column_name,
            existing_type=existing_type,
            existing_default=existing_default,
            existing_notnull=existing_notnull,
            modify_name=new_column_name,
            modify_type=type,
            modify_default=default,
            modify_notnull=notnull,
            **kw
        )

    def run(self):
        self.engine.alter_column(
            self.table_name, self.column_name, self.to_diff_tuple())


@Migration.register_operation("create_index")
class CreateIndexOp(Operation):
    def __init__(
        self, index_name, table_name, fields=[], expressions=[], unique=False,
        _orig_index=None, **kw
    ):
        self.index_name = index_name
        self.table_name = table_name
        self.fields = fields
        self.expressions = expressions
        self.unique = unique
        self.kw = kw
        self._orig_index = _orig_index

    def reverse(self):
        return DropIndexOp.from_index(self.to_index())

    def to_diff_tuple(self):
        return ("create_index", self.to_index())

    @classmethod
    def from_index(cls, index):
        return cls(
            index.name, index.table_name, index.fields, index.expressions,
            index.unique, _orig_index=index, **index.kw
        )

    def to_index(self):
        if self._orig_index is not None:
            return self._orig_index
        from .generation import MetaIndex
        return MetaIndex(
            self.table_name, self.index_name, self.fields, self.expressions,
            self.unique, **self.kw)

    @classmethod
    def create_index(
        cls, index_name, table_name, fields=[], expressions=[], unique=False,
        **kw
    ):
        return cls(index_name, table_name, fields, expressions, unique, **kw)

    def run(self):
        self.engine.create_index(
            self.index_name, self.table_name, self.fields, self.expressions,
            self.unique, **self.kw)


@Migration.register_operation("drop_index")
class DropIndexOp(Operation):
    def __init__(self, index_name, table_name=None, _orig_index=None):
        self.index_name = index_name
        self.table_name = table_name
        self._orig_index = _orig_index

    def to_diff_tuple(self):
        return ("remove_index", self.to_index())

    def reverse(self):
        if self._orig_index is None:
            raise ValueError(
                "operation is not reversible; "
                "original index is not present")
        return CreateIndexOp.from_index(self._orig_index)

    @classmethod
    def from_index(cls, index):
        return cls(index.name, index.table_name, index)

    def to_index(self):
        if self._orig_index is not None:
            return self._orig_index
        from .generation import MetaIndex
        return MetaIndex(self.table_name, self.index_name, [], [], False)

    @classmethod
    def drop_index(cls, index_name, table_name):
        return cls(index_name, table_name)

    def run(self):
        self.engine.drop_index(self.index_name, self.table_name)


# @Migration.register_operation("execute")
# class ExecuteSQLOp(Operation):
#     def __init__(self, sqltext):
#         self.sqltext = sqltext

#     def run(self):
#         pass
