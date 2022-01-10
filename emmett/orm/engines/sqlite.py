# -*- coding: utf-8 -*-
"""
    emmett.orm.engines.sqlite
    -------------------------

    Provides ORM SQLite engine specific features.

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

from pydal.adapters.sqlite import SQLite as _SQLite

from . import adapters


@adapters.register_for('sqlite', 'sqlite:memory')
class SQLite(_SQLite):
    def _initialize_(self, do_connect):
        super()._initialize_(do_connect)
        self.driver_args['isolation_level'] = None

    def begin(self, lock_type=None):
        statement = 'BEGIN %s;' % lock_type if lock_type else 'BEGIN;'
        self.execute(statement)

    def delete(self, table, query):
        deleted = (
            [x[table._id.name] for x in self.db(query).select(table._id)]
            if table._id else []
        )
        counter = super(_SQLite, self).delete(table, query)
        if table._id and counter:
            for field in table._referenced_by:
                if (
                    field.type == 'reference ' + table._dalname and
                    field.ondelete == 'CASCADE'
                ):
                    self.db(field.belongs(deleted)).delete()
        return counter
