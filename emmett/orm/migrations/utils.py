# -*- coding: utf-8 -*-
"""
    emmett.orm.migrations.utilities
    -------------------------------

    Provides some migration utilities.

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

from ..base import Database
from .engine import Engine
from .generation import Generator
from .operations import MigrationOp, UpgradeOps


class RuntimeGenerator(Generator):
    def _load_head_to_meta(self):
        pass


class RuntimeMigration(MigrationOp):
    def __init__(self, engine: Engine, ops: UpgradeOps):
        super().__init__('runtime', ops, ops.reverse(), 'runtime')
        self.engine = engine
        for op in self.upgrade_ops.ops:
            op.engine = self.engine
        for op in self.downgrade_ops.ops:
            op.engine = self.engine

    def up(self):
        for op in self.upgrade_ops.ops:
            op.run()

    def down(self):
        for op in self.downgrade_ops.ops:
            op.run()


def generate_runtime_migration(db: Database) -> RuntimeMigration:
    engine = Engine(db)
    upgrade_ops = RuntimeGenerator.generate_from(db, None, None)
    return RuntimeMigration(engine, upgrade_ops)
