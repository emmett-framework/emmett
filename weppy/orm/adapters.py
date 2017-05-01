# -*- coding: utf-8 -*-
"""
    weppy.orm.adapters
    ------------------

    Provides adapters facilities for dal.

    :copyright: (c) 2014-2017 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

from functools import wraps
from pydal.adapters import adapters
from pydal.adapters.mssql import (
    MSSQL1, MSSQL3, MSSQL4, MSSQL1N, MSSQL3N, MSSQL4N)
from pydal.adapters.postgres import (
    Postgre, PostgrePsyco, PostgrePG8000,
    PostgreNew, PostgrePsycoNew, PostgrePG8000New,
    PostgreBoolean, PostgrePsycoBoolean, PostgrePG8000Boolean
)
from .._compat import iteritems
from .objects import Field


adapters._registry_.update({
    'mssql': MSSQL4,
    'mssql2': MSSQL1,
    'mssql3': MSSQL3,
    'mssqln': MSSQL4N,
    'mssqln2': MSSQL1N,
    'mssqln3': MSSQL3N,
    'postgres': PostgreBoolean,
    'postgres:psycopg2': PostgrePsycoBoolean,
    'postgres:pg8000': PostgrePG8000Boolean,
    'postgres2': PostgreNew,
    'postgres2:psycopg2': PostgrePsycoNew,
    'postgres2:pg8000': PostgrePG8000New,
    'postgres3': Postgre,
    'postgres3:psycopg2': PostgrePsyco,
    'postgres3:pg8000': PostgrePG8000
})


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
    for name, table in iteritems(tables):
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
