# -*- coding: utf-8 -*-
"""
    weppy.orm.migrations.commands
    -----------------------------

    Provides command interfaces for migrations.

    :copyright: (c) 2014-2017 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

from ...utils import cachedprop
from ...datastructures import sdict
from ..base import Database
from .base import Schema, Column
from .helpers import make_migration_id, to_tuple
from .operations import MigrationOp, UpgradeOps, DowngradeOps
from .scripts import ScriptDir


class Command(object):
    def __init__(self, app, dals):
        self.app = app
        self.dals = dals
        self.scriptdir = ScriptDir(self.app)

    def load_schema(self, db):
        schema_db_config = sdict(uri=db.config.uri)
        self.schema_db = Database(
            self.app, schema_db_config, auto_connect=True,
            migrate=False, migrate_enabled=False)
        self.schema_db.define_models(Schema)
        self._ensure_schema_table_()
        self._load_current_revision_()

    def _ensure_schema_table_(self):
        # TODO -> has_table method in adapter, I don't like this "dirtness"
        try:
            self.schema_db(self.schema_db.Schema.id > 0).count()
        except Exception:
            self.schema_db.rollback()
            from .engine import Engine
            from .operations import CreateTableOp
            op = CreateTableOp.from_table(self._build_schema_metatable_())
            op.engine = Engine(self.schema_db)
            op.run()
            self.schema_db.commit()

    def _build_schema_metatable_(self):
        from .generation import MetaTable
        columns = []
        for field in list(self.schema_db.Schema):
            columns.append(Column.from_field(field))
        return MetaTable(
            self.schema_db.Schema._tablename,
            columns
        )

    def _load_current_revision_(self):
        revisions = self.schema_db(self.schema_db.Schema.id > 0).select()
        if not revisions:
            self._current_revision_ = []
        elif len(revisions) == 1:
            self._current_revision_ = [revisions[0].version]
        else:
            self._current_revision_ = [rev.version for rev in revisions]

    def _store_current_revision_(self, source, dest):
        logs = {
            'new': '> Adding revision %s to schema',
            'del': '> Removing revision %s from schema',
            'upd': '> Updating schema revision from %s to %s'}
        source = to_tuple(source)
        dest = to_tuple(dest)
        if source is None:
            print(logs['new'] % dest[0])
            self.schema_db.Schema.insert(version=dest[0])
            self.schema_db.commit()
            self._current_revision_ = [dest[0]]
            return
        if dest is None:
            print(logs['del'] % source[0])
            self.schema_db(self.schema_db.Schema.version == source[0]).delete()
            self.schema_db.commit()
            self._current_revision_ = []
            return
        if len(source) > 1:
            if len(source) > 2:
                self.schema_db(
                    self.schema_db.Schema.version.belongs(
                        source[1:])).delete()
                print(logs['del'] % source[1:])
            else:
                self.schema_db(
                    self.schema_db.Schema.version == source[1]).delete()
                print(logs['del'] % source[1])
            self.schema_db(self.schema_db.Schema.version == source[0]).update(
                version=dest[0]
            )
            print(logs['upd'] % (source[0], dest[0]))
            self._current_revision_ = [dest[0]]
        else:
            if list(source) != self._current_revision_:
                self.schema_db.Schema.insert(version=dest[0])
                print(logs['new'] % dest[0])
                self._current_revision_.append(dest[0])
            else:
                self.schema_db(
                    self.schema_db.Schema.version == source[0]
                ).update(
                    version=dest[0]
                )
                print(logs['upd'] % (source[0], dest[0]))
                self._current_revision_ = [dest[0]]
        self.schema_db.commit()

    @cachedprop
    def db(self):
        if len(self.dals) == 1:
            return self.dals[0]
        return self.dals

    def _generate_migration_script(self, migration, head):
        from .generation import Renderer
        upgrades, downgrades = Renderer.render_migration(migration)
        self.scriptdir.generate_revision(
            migration.rev_id, migration.message, head, upgrades=upgrades,
            downgrades=downgrades
        )

    def generate(self, message, head):
        if len(self.dals) > 1:
            raise RuntimeError('need just one db instance')
        from .generation import Generator
        upgrade_ops = Generator.generate_from(self.db, self.scriptdir, head)
        revid = make_migration_id()
        migration = MigrationOp(
            revid, upgrade_ops, upgrade_ops.reverse(), message)
        self._generate_migration_script(migration, head)
        print("> Generated migration for revision %s" % revid)

    def new(self, message, head):
        source_rev = self.scriptdir.get_revision(head)
        revid = make_migration_id()
        migration = MigrationOp(
            revid, UpgradeOps(), DowngradeOps(), message
        )
        self._generate_migration_script(migration, source_rev.revision)
        print("> Created new migration with revision %s" % revid)

    def history(self, base, head, verbose):
        print("> Migrations history")
        lines = []
        for sc in self.scriptdir.walk_revisions(
                base=base or "base",
                head=head or "heads"):
            lines.append(
                sc.cmd_format(
                    verbose=verbose, include_doc=True, include_parents=True))
        for line in lines:
            print(line)
        if not lines:
            print("No migrations for the selected application.")

    def status(self, verbose):
        self.load_schema(self.db)
        print("> Current revision(s) for %s" % self.db._uri)
        lines = []
        for rev in self.scriptdir.get_revisions(self._current_revision_):
            lines.append(rev.cmd_format(verbose))
        for line in lines:
            print(line)
        if not lines:
            print("No revision state found on the schema.")

    def up(self, rev_id):
        self.load_schema(self.db)
        start_point = self._current_revision_
        revisions = self.scriptdir.get_upgrade_revs(
            rev_id, start_point)
        print("> Performing upgrades against %s" % self.db._uri)
        for revision in revisions:
            print("> Performing upgrade: %s" % revision)
            migration = revision.migration_class(self.app, self.db)
            try:
                migration.up()
                self.db.commit()
                self._store_current_revision_(
                    migration.revises, migration.revision)
                print("> Succesfully upgraded to revision %s: %s" %
                      (revision.revision, revision.doc))
            except Exception:
                self.db.rollback()
                print("> [ERROR] failed upgrading to %s" % revision)
                raise

    def down(self, rev_id):
        self.load_schema(self.db)
        start_point = self._current_revision_
        revisions = self.scriptdir.get_downgrade_revs(
            rev_id, start_point)
        print("> Performing downgrades against %s" % self.db._uri)
        for revision in revisions:
            print("> Performing downgrade: %s" % revision)
            migration = revision.migration_class(self.app, self.db)
            try:
                migration.down()
                self.db.commit()
                self._store_current_revision_(
                    migration.revision, migration.revises)
                print("> Succesfully downgraded from revision %s: %s" %
                      (revision.revision, revision.doc))
            except Exception:
                self.db.rollback()
                print("> [ERROR] failed downgrading from %s" % revision)
                raise


def generate(app, dals, message, head):
    Command(app, dals).generate(message, head)


def new(app, dals, message, head):
    Command(app, dals).new(message, head)


def history(app, dals, rev_range, verbose):
    if rev_range is not None:
        if ":" not in rev_range:
            raise Exception(
                "History range requires [start]:[end], "
                "[start]:, or :[end]")
        base, head = rev_range.strip().split(":")
    else:
        base = head = None
    Command(app, dals).history(base, head, verbose)


def status(app, dals, verbose):
    Command(app, dals).status(verbose)


def up(app, dals, revision):
    Command(app, dals).up(revision)


def down(app, dals, revision):
    Command(app, dals).down(revision)
