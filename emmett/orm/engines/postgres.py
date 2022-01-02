# -*- coding: utf-8 -*-
"""
    emmett.orm.engines.postgres
    ---------------------------

    Provides ORM PostgreSQL engine specific features.

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

from pydal.adapters.postgres import (
    PostgreBoolean,
    PostgrePsycoBoolean,
    PostgrePG8000Boolean
)
from pydal.dialects import register_expression, sqltype_for
from pydal.dialects.postgre import PostgreDialectBooleanJSON
from pydal.helpers.serializers import serializers
from pydal.objects import Expression, Query
from pydal.parsers import for_type as parse_type
from pydal.parsers.postgre import PostgreBooleanAutoJSONParser
from pydal.representers import for_type as repr_type
from pydal.representers.postgre import PostgreArraysRepresenter

from . import adapters


class JSONBPostgreDialect(PostgreDialectBooleanJSON):
    @sqltype_for('jsonb')
    def type_jsonb(self):
        return 'jsonb'

    def _jcontains(self, field, data, query_env={}):
        return '(%s @> %s)' % (
            self.expand(field, query_env=query_env),
            self.expand(data, field.type, query_env=query_env)
        )

    @register_expression('jcontains')
    def _jcontains_expr(self, expr, data):
        return Query(expr.db, self._jcontains, expr, data)

    def _jin(self, field, data, query_env={}):
        return '(%s <@ %s)' % (
            self.expand(field, query_env=query_env),
            self.expand(data, field.type, query_env=query_env)
        )

    @register_expression('jin')
    def _jin_expr(self, expr, data):
        return Query(expr.db, self._jin, expr, data)

    def _jget_common(self, op, field, data, query_env):
        if not isinstance(data, int):
            _dtype = field.type if isinstance(data, (dict, list)) else 'string'
            data = self.expand(data, field_type=_dtype, query_env=query_env)
        return '%s %s %s' % (
            self.expand(field, query_env=query_env),
            op,
            str(data)
        )

    def _jget(self, field, data, query_env={}):
        return self._jget_common('->', field, data, query_env=query_env)

    @register_expression('jget')
    def _jget_expr(self, expr, data):
        return Expression(expr.db, self._jget, expr, data, expr.type)

    def _jgetv(self, field, data, query_env={}):
        return self._jget_common('->>', field, data, query_env=query_env)

    @register_expression('jgetv')
    def _jgetv_expr(self, expr, data):
        return Expression(expr.db, self._jgetv, expr, data, 'string')

    def _jpath(self, field, data, query_env={}):
        return '%s #> %s' % (
            self.expand(field, query_env=query_env),
            self.expand(data, field_type='string', query_env=query_env)
        )

    @register_expression('jpath')
    def _jpath_expr(self, expr, data):
        return Expression(expr.db, self._jpath, expr, data, expr.type)

    def _jpathv(self, field, data, query_env={}):
        return '%s #>> %s' % (
            self.expand(field, query_env=query_env),
            self.expand(data, field_type='string', query_env=query_env)
        )

    @register_expression('jpathv')
    def _jpathv_expr(self, expr, data):
        return Expression(expr.db, self._jpathv, expr, data, 'string')

    def _jhas(self, field, data, all=False, query_env={}):
        _op, _ftype = '?', 'string'
        if isinstance(data, list):
            _op = '?&' if all else '?|'
            _ftype = 'list:string'
        return '%s %s %s' % (
            self.expand(field, query_env=query_env),
            _op,
            self.expand(data, field_type=_ftype, query_env=query_env)
        )

    @register_expression('jhas')
    def _jhas_expr(self, expr, data, all=False):
        return Query(expr.db, self._jhas, expr, data, all=all)


class JSONBPostgreParser(PostgreBooleanAutoJSONParser):
    @parse_type('jsonb')
    def _jsonb(self, value):
        return value


class JSONBPostgreRepresenter(PostgreArraysRepresenter):
    @repr_type('jsonb')
    def _jsonb(self, value):
        return serializers.json(value)


class PostgresAdapterMixin:
    def _load_dependencies(self):
        super()._load_dependencies()
        self.dialect = JSONBPostgreDialect(self)
        self.parser = JSONBPostgreParser(self)
        self.representer = JSONBPostgreRepresenter(self)

    def _config_json(self):
        pass

    def _mock_reconnect(self):
        pass

    def _insert(self, table, fields):
        self._last_insert = None
        if fields:
            retval = None
            if getattr(table, "_id", None):
                self._last_insert = (table._id, 1)
                retval = table._id._rname
            return self.dialect.insert(
                table._rname,
                ','.join(el[0]._rname for el in fields),
                ','.join(self.expand(v, f.type) for f, v in fields),
                retval
            )
        return self.dialect.insert_empty(table._rname)

    def lastrowid(self, table):
        if self._last_insert:
            return self.cursor.fetchone()[0]
        sequence_name = table._sequence_name
        self.execute("SELECT currval(%s);" % self.adapt(sequence_name))
        return self.cursor.fetchone()[0]


@adapters.register_for('postgres')
class PostgresAdapter(PostgresAdapterMixin, PostgreBoolean):
    pass


@adapters.register_for('postgres:psycopg2')
class PostgresPsycoPG2Adapter(PostgresAdapterMixin, PostgrePsycoBoolean):
    pass


@adapters.register_for('postgres:pg8000')
class PostgresPG8000Adapter(PostgresAdapterMixin, PostgrePG8000Boolean):
    pass
