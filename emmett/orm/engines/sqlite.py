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
        super(SQLite, self)._initialize_(do_connect)
        self.driver_args['isolation_level'] = None

    def begin(self, lock_type=None):
        statement = 'BEGIN %s;' % lock_type if lock_type else 'BEGIN;'
        self.execute(statement)
