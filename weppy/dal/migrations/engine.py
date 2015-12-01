# -*- coding: utf-8 -*-
"""
    weppy.dal.migrations.engine
    ---------------------------

    Provides migration engine for pyDAL.

    :copyright: (c) 2015 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""


class MetaEngine(object):
    def __init__(self, db):
        self.db = db

    def create_table(self, name, columns, **kwargs):
        self.db.create_table(name, columns)


class Engine(MetaEngine):
    @property
    def adapter(self):
        return self.db._adapter

    def create_table(self, name, columns, **kwargs):
        params = {}
        for key in ['primary_keys', 'id_col']:
            if kwargs.get(key) is not None:
                params[key] = kwargs[key]
        sql = self._new_table_sql(name, columns, **params)
        print(sql)
        self.db._adapter.execute(sql)

    def _gen_reference(self, tablename, column):
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
                pass
        else:
            csql_info = dict(
                index_name=self.adapter.QUOTE_TEMPLATE % (column.name+'__idx'),
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
        return self.adapter.types[geotype]

    def _new_table_sql(self, tablename, columns, primary_keys=[], id_col='id'):
        ## TODO:
        ##      postgres geometry
        ##      SQLCustomType
        fields = []
        for sortable, column in enumerate(columns, start=1):
            if column.type.startswith(('reference', 'big-reference')):
                csql = self._gen_reference(tablename, column)
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

            if not column.type.startswith(('id', 'reference', 'big-reference')):
                if column.notnull:
                    csql += ' NOT NULL'
                else:
                    csql += self.adapter.ALLOW_NULL()
                if column.unique:
                    csql += ' UNIQUE'
                if column.custom_qualifier:
                    csql += ' %s' % column.custom_qualifier

            if column.notnull and column.default is not None:
                not_null = self.adapter.NOT_NULL(column.default, column.type)
                csql = csql.replace('NOT NULL', not_null)

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
