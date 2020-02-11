# -*- coding: utf-8 -*-
"""
    emmett.orm.adapters
    -------------------

    Provides ORM adapters facilities.

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

from functools import wraps
from pydal.adapters import adapters
from pydal.adapters.mssql import (
    MSSQL1, MSSQL3, MSSQL4, MSSQL1N, MSSQL3N, MSSQL4N
)
from pydal.adapters.postgres import (
    Postgre, PostgrePsyco, PostgrePG8000,
    PostgreNew, PostgrePsycoNew, PostgrePG8000New,
    PostgreBoolean, PostgrePsycoBoolean, PostgrePG8000Boolean
)
from pydal.adapters.sqlite import SQLite as _SQLite
from pydal.dialects.postgre import PostgreDialectBooleanJSON
from pydal.parsers.postgre import PostgreBooleanAutoJSONParser

from .objects import Field


adapters._registry_.update({
    'mssql': MSSQL4,
    'mssql2': MSSQL1,
    'mssql3': MSSQL3,
    'mssqln': MSSQL4N,
    'mssqln2': MSSQL1N,
    'mssqln3': MSSQL3N,
    'postgres2': PostgreNew,
    'postgres2:psycopg2': PostgrePsycoNew,
    'postgres2:pg8000': PostgrePG8000New,
    'postgres3': Postgre,
    'postgres3:psycopg2': PostgrePsyco,
    'postgres3:pg8000': PostgrePG8000
})


@adapters.register_for('sqlite', 'sqlite:memory')
class SQLite(_SQLite):
    def _initialize_(self, do_connect):
        super(SQLite, self)._initialize_(do_connect)
        self.driver_args['isolation_level'] = None

    def begin(self, lock_type=None):
        statement = 'BEGIN %s;' % lock_type if lock_type else 'BEGIN;'
        self.execute(statement)


@adapters.register_for('postgres')
class PostgresAdapter(PostgreBoolean):
    def _load_dependencies(self):
        super()._load_dependencies()
        self.dialect = PostgreDialectBooleanJSON(self)
        self.parser = PostgreBooleanAutoJSONParser(self)

    def _config_json(self):
        pass

    def _mock_reconnect(self):
        pass


@adapters.register_for('postgres:psycopg2')
class PostgresPsycoPG2Adapter(PostgrePsycoBoolean):
    def _load_dependencies(self):
        super()._load_dependencies()
        self.dialect = PostgreDialectBooleanJSON(self)
        self.parser = PostgreBooleanAutoJSONParser(self)

    def _config_json(self):
        pass

    def _mock_reconnect(self):
        pass


@adapters.register_for('postgres:pg8000')
class PostgresPG8000Adapter(PostgrePG8000Boolean):
    def _load_dependencies(self):
        super()._load_dependencies()
        self.dialect = PostgreDialectBooleanJSON(self)
        self.parser = PostgreBooleanAutoJSONParser(self)

    def _config_json(self):
        pass

    def _mock_reconnect(self):
        pass


def _wrap_on_obj(f, adapter):
    @wraps(f)
    def wrapped(*args, **kwargs):
        return f(adapter, *args, **kwargs)
    return wrapped


def patch_adapter(adapter):
    adapter.parse = _wrap_on_obj(parse, adapter)
    adapter._parse_expand_colnames = _wrap_on_obj(
        _parse_expand_colnames, adapter)
    adapter._parse = _wrap_on_obj(_parse, adapter)
    patch_dialect(adapter.dialect)


def patch_dialect(dialect):
    _create_table_map = {
        'mysql': _create_table_mysql,
        'firebird': _create_table_firebird
    }
    dialect.create_table = _wrap_on_obj(
        _create_table_map.get(dialect.adapter.dbengine, _create_table),
        dialect)


def parse(adapter, rows, fields, colnames, blob_decode=True, cacheable=False):
    fdata, tables = _parse_expand_colnames(adapter, fields)
    new_rows = [
        _parse(adapter, row, fdata, tables, fields, colnames, blob_decode)
        for row in rows
    ]
    rowsobj = adapter.db.Rows(adapter.db, new_rows, colnames, rawrows=rows)
    return rowsobj


def _parse_expand_colnames(adapter, fieldlist):
    rv, tables = [], {}
    for field in fieldlist:
        if not isinstance(field, Field):
            rv.append(None)
            continue
        table = field.table
        tablename, fieldname = table._tablename, field.name
        ft = field.type
        fit = field._itype
        rv.append((tablename, fieldname, table, field, ft, fit))
        tables[tablename] = table
    return rv, tables


def _parse(adapter, row, fdata, tables, fields, colnames, blob_decode):
    new_row = _build_newrow_wtables(adapter, tables)
    extras = adapter.db.Row()
    #: let's loop over columns
    for (idx, colname) in enumerate(colnames):
        value = row[idx]
        fd = fdata[idx]
        tablename = None
        #: do we have a real column?
        if fd:
            (tablename, fieldname, table, field, ft, fit) = fd
            colset = new_row[tablename]
            #: parse value
            value = adapter.parse_value(value, fit, ft, blob_decode)
            if field.filter_out:
                value = field.filter_out(value)
            colset[fieldname] = value
        #: otherwise we set the value in extras
        else:
            value = adapter.parse_value(
                value, fields[idx]._itype, fields[idx].type, blob_decode)
            extras[colname] = value
            new_column_name = adapter._regex_select_as_parser(colname)
            if new_column_name is not None:
                column_name = new_column_name.groups(0)
                new_row[column_name[0]] = value
    #: add extras if needed (eg. operations results)
    if extras:
        new_row['_extra'] = extras
    return new_row


def _build_newrow_wtables(adapter, tables):
    rv = adapter.db.Row()
    for name, table in tables.items():
        rv[name] = table._model_._rowclass_()
    return rv


def _create_table(dialect, tablename, fields):
    return [
        "CREATE TABLE %s(\n    %s\n);" % (dialect.quote(tablename), fields)]


def _create_table_mysql(dialect, tablename, fields):
    return ["CREATE TABLE %s(\n    %s\n) ENGINE=%s CHARACTER SET utf8;" % (
        dialect.quote(tablename), fields,
        dialect.adapter.adapter_args.get('engine', 'InnoDB'))]


def _create_table_firebird(dialect, tablename, fields):
    rv = _create_table(dialect, tablename, fields)
    sequence_name = dialect.sequence_name(tablename)
    trigger_name = dialect.trigger_name(tablename)
    trigger_sql = (
        'create trigger %s for %s active before insert position 0 as\n'
        'begin\n'
        'if(new."id" is null) then\n'
        'begin\n'
        'new."id" = gen_id(%s, 1);\n'
        'end\n'
        'end;')
    rv.extend([
        'create generator %s;' % sequence_name,
        'set generator %s to 0;' % sequence_name,
        trigger_sql % (trigger_name, dialect.quote(tablename), sequence_name)
    ])
    return rv


def _initialize(adapter, *args, **kwargs):
    adapter._find_work_folder()
    adapter._connection_manager.configure(
        max_connections=adapter.db._pool_size,
        connect_timeout=adapter.db._connect_timeout,
        stale_timeout=adapter.db._keep_alive_timeout)


def _begin(adapter):
    pass


def _in_transaction(adapter):
    return bool(adapter._connection_manager.state.transactions)


def _push_transaction(adapter, transaction):
    adapter._connection_manager.state.transactions.append(transaction)


def _pop_transaction(adapter):
    adapter._connection_manager.state.transactions.pop()


def _transaction_depth(adapter):
    return len(adapter._connection_manager.state.transactions)


def _top_transaction(adapter):
    if adapter._connection_manager.state.transactions:
        return adapter._connection_manager.state.transactions[-1]
