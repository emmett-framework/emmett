# -*- coding: utf-8 -*-
"""
    weppy.dal.migrations.engine
    ---------------------------

    Provides migration engine for pyDAL.

    :copyright: (c) 2014-2016 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

from ..._compat import iteritems
from ...datastructures import sdict


class MetaEngine(object):
    def __init__(self, db):
        self.db = db

    def create_table(self, name, columns, **kwargs):
        self.db.create_table(name, columns)

    def drop_table(self, name):
        self.db.drop_table(name)

    def add_column(self, table_name, column):
        self.db.add_column(table_name, column)

    def drop_column(self, table_name, column_name):
        self.db.drop_column(table_name, column_name)

    def alter_column(self, table_name, column_name, changes):
        pchanges = self._parse_column_changes(changes)
        updates = {k: v[1] for k, v in iteritems(pchanges)}
        self.db.change_column(table_name, column_name, updates)

    @staticmethod
    def _parse_column_changes(changes):
        rv = {}
        for change in changes:
            if change[0] == "modify_type":
                rv['type'] = [change[4], change[5]]
            elif change[0] == "modify_notnull":
                rv['notnull'] = [change[4], change[5]]
            elif change[0] == "modify_default":
                rv['default'] = [
                    change[4], change[5], change[3]['existing_type']]
        return rv


class Engine(MetaEngine):
    @property
    def adapter(self):
        return self.db._adapter

    def _log_and_exec(self, sql):
        self.db.logger.debug("executing SQL:\n%s" % sql)
        self.adapter.execute(sql)

    def create_table(self, name, columns, **kwargs):
        params = {}
        for key in ['primary_keys', 'id_col']:
            if kwargs.get(key) is not None:
                params[key] = kwargs[key]
        sql = self._new_table_sql(name, columns, **params)
        self._log_and_exec(sql)

    def drop_table(self, name):
        adapt_v = sdict(sqlsafe=name)
        sql_list = self.adapter._drop(adapt_v, '')
        for sql in sql_list:
            self._log_and_exec(sql)

    def add_column(self, tablename, column):
        sql = self._add_column_sql(tablename, column)
        self._log_and_exec(sql)

    def drop_column(self, tablename, colname):
        sql = self._drop_column_sql(tablename, colname)
        self._log_and_exec(sql)

    def alter_column(self, table_name, column_name, changes):
        sql = self._alter_column_sql(
            table_name, column_name, self._parse_column_changes(changes))
        if sql is not None:
            self._log_and_exec(sql)

    def _quote(self, v):
        return self.adapter.QUOTE_TEMPLATE % v

    def _gen_reference(self, tablename, column, tfks):
        if column.type.startswith('reference'):
            referenced = column.type[10:].strip()
            type_name = 'reference'
        else:
            referenced = column.type[14:].strip()
            type_name = 'big-reference'
        constraint_name = self.adapter.constraint_name(tablename, column.name)
        try:
            rtablename, rfieldname = referenced.split('.')
        except:
            rtablename = referenced
            rfieldname = 'id'
        if not rtablename:
            rtablename = tablename
        if column.fk or column.tfk:
            csql = self.adapter.types[column.type[:9]] % \
                dict(length=column.length)
            if column.fk:
                fk_name = rtablename + ' (' + rfieldname + ')'
                csql = csql + self.adapter.types['reference FK'] % dict(
                    constraint_name=constraint_name,
                    foreign_key=fk_name,
                    table_name=tablename,
                    field_name=column.name,
                    on_delete_action=column.ondelete)
            if column.tfk:
                # TODO
                raise NotImplementedError(
                    'Migrating tables containing multiple columns references' +
                    ' is currently not supported.'
                )
        else:
            csql_info = dict(
                index_name=self.adapter.QUOTE_TEMPLATE % (column.name + '__idx'),
                field_name=rfieldname,
                constraint_name=self.adapter.QUOTE_TEMPLATE % constraint_name,
                foreign_key='%s (%s)' % (rtablename, rfieldname),
                on_delete_action=column.ondelete)
            csql_info['null'] = ' NOT NULL' if column.notnull else \
                self.adapter.ALLOW_NULL()
            csql_info['unique'] = ' UNIQUE' if column.unique else ''
            csql = self.adapter.types[type_name] % csql_info
        return csql

    def _gen_primary_key(self, fields, primary_keys=[]):
        if primary_keys:
            fields.append(self.db.PRIMARY_KEY(
                ', '.join([
                    self.db.QUOTE_TEMPLATE % pk for pk in primary_keys])))

    def _gen_geo(self, tablename, column):
        if not hasattr(self.adapter, 'srid'):
            raise RuntimeError('Adapter does not support geometry')
        geotype, parms = column.type[:-1].split('(')
        if geotype not in self.adapter.types:
            raise SyntaxError(
                'Field: unknown field type: %s for %s' %
                (column.type, column.name))
        if self.adaper.dbengine == 'postgres' and geotype == 'geometry':
            # TODO
            raise NotImplementedError(
                'Migration with PostgreSQL and %s columns are not supported.' %
                column.type
            )
        return self.adapter.types[geotype]

    def _new_column_sql(self, tablename, column, tfks):
        if column.type.startswith(('reference', 'big-reference')):
            csql = self._gen_reference(tablename, column, tfks)
        elif column.type.startswith('list:reference'):
            csql = self.adapter.types[column.type[:14]]
        elif column.type.startswith('decimal'):
            precision, scale = map(int, column.type[8:-1].split(','))
            csql = self.adapter.types[column.type[:7]] % \
                dict(precision=precision, scale=scale)
        elif column.type.startswith('geo'):
            csql = self._gen_geo()
        elif column.type not in self.adapter.types:
            raise SyntaxError(
                'Field: unknown field type: %s for %s' %
                (column.type, column.name))
        else:
            csql = self.adapter.types[column.type] % \
                {'length': column.length}
        if self.adapter.dbengine not in ('firebird', 'informix', 'oracle'):
            cprops = "%(notnull)s%(default)s%(unique)s%(qualifier)s"
        else:
            cprops = "%(default)s%(notnull)s%(unique)s%(qualifier)s"
        if not column.type.startswith(('id', 'reference', 'big-reference')):
            csql += cprops % {
                'notnull': ' NOT NULL' if column.notnull
                           else self.adapter.ALLOW_NULL(),
                'default': ' DEFAULT %s' %
                           self.adapter.represent(column.default, column.type)
                           if column.default is not None else '',
                'unique': ' UNIQUE' if column.unique else '',
                'qualifier': ' %s' % column.custom_qualifier
                             if column.custom_qualifier else ''
            }
        #     if column.notnull:
        #         csql += ' NOT NULL'
        #     else:
        #         csql += self.adapter.ALLOW_NULL()
        #     if column.unique:
        #         csql += ' UNIQUE'
        #     if column.custom_qualifier:
        #         csql += ' %s' % column.custom_qualifier
        # if column.notnull and column.default is not None:
        #     not_null = self.adapter.NOT_NULL(column.default, column.type)
        #     csql = csql.replace('NOT NULL', not_null)
        return csql

    def _new_table_sql(self, tablename, columns, primary_keys=[], id_col='id'):
        # TODO:
        # - postgres geometry
        # - SQLCustomType
        fields = []
        tfks = {}
        for sortable, column in enumerate(columns, start=1):
            csql = self._new_column_sql(tablename, column, tfks)
            fields.append('%s %s' % (column.name, csql))
        extras = ''
        # backend-specific extensions to fields
        if self.adapter.dbengine == 'mysql':
            if not primary_keys:
                primary_keys.append(id_col)
            engine = self.db.adapter_args.get('engine', 'InnoDB')
            extras += ' ENGINE=%s CHARACTER SET utf8' % engine

        self._gen_primary_key(fields, primary_keys)
        fields = ',\n    '.join(fields)
        return "CREATE TABLE %s(\n    %s\n)%s;" % (tablename, fields, extras)

    def _add_column_sql(self, tablename, column):
        csql = self._new_column_sql(tablename, column, {})
        return 'ALTER TABLE %(tname)s ADD %(cname)s %(sql)s;' % {
            'tname': self._quote(tablename),
            'cname': self._quote(column.name), 'sql': csql
        }

    def _drop_column_sql(self, table_name, column_name):
        if self.adapter.dbengine == "firebird":
            sql = 'ALTER TABLE %s DROP %s;'
        else:
            sql = 'ALTER TABLE %s DROP COLUMN %s;'
        return sql % (self._quote(table_name), self._quote(column_name))

    def _feasible_as_changed_type(self, oldv, newv, clen):
        old_sqltype = self.adapter.types[oldv] % {'length': clen}
        new_sqltype = self.adapter.types[newv] % {'length': clen}
        return old_sqltype != new_sqltype

    def _represent_changes(self, changes, col_len):
        if 'default' in changes and changes['default'][1] is not None:
            ftype = changes['default'][2]
            if 'type' in changes:
                ftype = changes['type'][1]
            changes['default'][1] = self.represent(
                changes['default'][1], ftype)
        if 'type' in changes:
            if not self._feasible_as_changed_type(changes['type'][0], changes['type'][1], col_len):
                del changes['type']
                return
            coltype = changes['type'][1]
            if coltype.startswith(('reference', 'big-reference')):
                raise NotImplementedError(
                    'Type change on reference fields is not supported.'
                )
            elif coltype.startswith('decimal'):
                precision, scale = map(int, coltype[8:-1].split(','))
                csql = self.adapter.types[coltype[:7]] % \
                    dict(precision=precision, scale=scale)
            elif coltype.startswith('geo'):
                csql = self._gen_geo()
            else:
                csql = self.adapter.types[coltype] % \
                    {'length': col_len}
            changes['type'][1] = csql

    def _alter_column_sql(self, table_name, column_name, changes):
        sql = 'ALTER_TABLE %(tname)s ALTER COLUMN %(cname)s %(changes)s;'
        sql_changes_map = {
            'type': "TYPE %s",
            'notnull': {
                True: "SET NOT NULL",
                False: "DROP NOT NULL"
            },
            'default': ["SET DEFAULT %s", "DROP DEFAULT"]
        }
        col_len = self.db[table_name][column_name].length
        self._represent_changes(changes, col_len)
        sql_changes = []
        for change_type, change_val in iteritems(changes):
            change_sql = sql_changes_map[change_type]
            if isinstance(change_sql, dict):
                sql_changes.append(change_sql[change_val[1]])
            elif isinstance(change_sql, list):
                sql_changes.append(
                    change_sql[0] % change_val[1] if change_val[1] is not None
                    else change_sql[1])
            else:
                sql_changes.append(change_sql % change_val[1])
        if not sql_changes:
            return None
        return sql % {
            'tname': self._quote(table_name),
            'cname': self._quote(column_name),
            'changes': " ".join(sql_changes)
        }
