# -*- coding: utf-8 -*-
"""
    emmett.orm.migrations.engine
    ----------------------------

    Provides migration engine for pyDAL.

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

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
        updates = {k: v[1] for k, v in pchanges.items()}
        self.db.change_column(table_name, column_name, updates)

    def create_index(self, name, table_name, fields, expr, unique, **kw):
        self.db.create_index(table_name, name, fields, expr, unique, **kw)

    def drop_index(self, name, table_name):
        self.db.drop_index(table_name, name)

    @staticmethod
    def _parse_column_changes(changes):
        rv = {}
        for change in changes:
            if change[0] == "modify_type":
                rv['type'] = [
                    change[4], change[5], change[3]['existing_length']
                ]
            elif change[0] == "modify_length":
                rv['length'] = [
                    change[4], change[5], change[3]['existing_type']
                ]
            elif change[0] == "modify_notnull":
                rv['notnull'] = [change[4], change[5]]
            elif change[0] == "modify_default":
                rv['default'] = [
                    change[4], change[5], change[3]['existing_type']
                ]
        return rv


class Engine(MetaEngine):
    @property
    def adapter(self):
        return self.db._adapter

    @property
    def dialect(self):
        return self.db._adapter.dialect

    def _log_and_exec(self, sql):
        self.db.logger.debug("executing SQL:\n%s" % sql)
        self.adapter.execute(sql)

    def create_table(self, name, columns, **kwargs):
        params = {}
        for key in ['primary_keys', 'id_col']:
            if kwargs.get(key) is not None:
                params[key] = kwargs[key]
        sql_list = self._new_table_sql(name, columns, **params)
        for sql in sql_list:
            self._log_and_exec(sql)

    def drop_table(self, name):
        adapt_v = sdict(_rname=self.dialect.quote(name))
        sql_list = self.dialect.drop_table(adapt_v, 'cascade')
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

    def create_index(self, name, table_name, fields, expr, unique, **kw):
        adapt_t = sdict(_rname=self.dialect.quote(table_name))
        components = [self.dialect.quote(field) for field in fields]
        components += expr
        sql = self.dialect.create_index(
            name, adapt_t, components, unique, **kw)
        self._log_and_exec(sql)

    def drop_index(self, name, table_name):
        adapt_t = sdict(_rname=self.dialect.quote(table_name))
        sql = self.dialect.drop_index(name, adapt_t)
        self._log_and_exec(sql)

    def _gen_reference(self, tablename, column, tfks):
        referenced = column.type[10:].strip()
        constraint_name = self.dialect.constraint_name(tablename, column.name)
        try:
            rtablename, rfieldname = referenced.split('.')
        except Exception:
            rtablename = referenced
            rfieldname = 'id'
        if not rtablename:
            rtablename = tablename
        if column.fk or column.tfk:
            csql = self.adapter.types[column.type[:9]] % \
                dict(length=column.length)
            if column.fk:
                csql = csql + self.adapter.types['reference FK'] % dict(
                    constraint_name=self.dialect.quote(constraint_name),
                    foreign_key='%s (%s)' % (
                        self.dialect.quote(rtablename),
                        self.dialect.quote(rfieldname)),
                    table_name=self.dialect.quote(tablename),
                    field_name=self.dialect.quote(column.name),
                    on_delete_action=column.ondelete)
            if column.tfk:
                # TODO
                raise NotImplementedError(
                    'Migrating tables containing multiple columns references '
                    'is currently not supported.'
                )
        else:
            csql_info = dict(
                index_name=self.dialect.quote(column.name + '__idx'),
                field_name=self.dialect.quote(column.name),
                constraint_name=self.dialect.quote(constraint_name),
                foreign_key='%s (%s)' % (
                    self.dialect.quote(rtablename),
                    self.dialect.quote(rfieldname)),
                on_delete_action=column.ondelete)
            csql_info['null'] = ' NOT NULL' if column.notnull else \
                self.dialect.allow_null
            csql_info['unique'] = ' UNIQUE' if column.unique else ''
            csql = self.adapter.types['reference'] % csql_info
        return csql

    def _gen_primary_key(self, fields, primary_keys=[]):
        if primary_keys:
            fields.append(self.dialect.primary_key(
                ', '.join([
                    self.dialect.quote(pk) for pk in primary_keys])))

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
        if column.type.startswith('reference'):
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
        if not column.type.startswith(('id', 'reference')):
            csql += cprops % {
                'notnull': ' NOT NULL' if column.notnull
                           else self.dialect.allow_null,
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
            fields.append('%s %s' % (self.dialect.quote(column.name), csql))
        # backend-specific extensions to fields
        if self.adapter.dbengine == 'mysql':
            if not primary_keys:
                primary_keys.append(id_col)

        self._gen_primary_key(fields, primary_keys)
        fields = ',\n    '.join(fields)
        return self.dialect.create_table(tablename, fields)

    def _add_column_sql(self, tablename, column):
        csql = self._new_column_sql(tablename, column, {})
        return 'ALTER TABLE %(tname)s ADD %(cname)s %(sql)s;' % {
            'tname': self.dialect.quote(tablename),
            'cname': self.dialect.quote(column.name),
            'sql': csql
        }

    def _drop_column_sql(self, table_name, column_name):
        if self.adapter.dbengine == "firebird":
            sql = 'ALTER TABLE %s DROP %s;'
        else:
            sql = 'ALTER TABLE %s DROP COLUMN %s;'
        return sql % (
            self.dialect.quote(table_name), self.dialect.quote(column_name))

    def _represent_changes(self, changes, field):
        if 'default' in changes and changes['default'][1] is not None:
            ftype = changes['default'][2] or field.type
            if 'type' in changes:
                ftype = changes['type'][1]
            changes['default'][1] = self.adapter.represent(
                changes['default'][1], ftype)
        if 'type' in changes:
            changes.pop('length', None)
            coltype = changes['type'][1]
            if coltype.startswith('reference'):
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
                csql = self.adapter.types[coltype] % {
                    'length': changes['type'][2] or field.length
                }
            changes['type'][1] = csql
        elif 'length' in changes:
            change = changes.pop('length')
            ftype = change[2] or field.type
            changes['type'] = [
                None,
                self.adapter.types[ftype] % {'length': change[1]}
            ]

    def _alter_column_sql(self, table_name, column_name, changes):
        sql = 'ALTER TABLE %(tname)s ALTER COLUMN %(cname)s %(changes)s;'
        sql_changes_map = {
            'type': "TYPE %s",
            'notnull': {
                True: "SET NOT NULL",
                False: "DROP NOT NULL"
            },
            'default': ["SET DEFAULT %s", "DROP DEFAULT"]
        }
        field = self.db[table_name][column_name]
        self._represent_changes(changes, field)
        sql_changes = []
        for change_type, change_val in changes.items():
            change_sql = sql_changes_map[change_type]
            if isinstance(change_sql, dict):
                sql_changes.append(change_sql[change_val[1]])
            elif isinstance(change_sql, list):
                sql_changes.append(
                    change_sql[0] % change_val[1] if change_val[1] is not None
                    else change_sql[1]
                )
            else:
                sql_changes.append(change_sql % change_val[1])
        if not sql_changes:
            return None
        return sql % {
            'tname': self.dialect.quote(table_name),
            'cname': self.dialect.quote(column_name),
            'changes': " ".join(sql_changes)
        }
