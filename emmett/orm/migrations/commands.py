# -*- coding: utf-8 -*-
"""
    emmett.orm.migrations.commands
    ------------------------------

    Provides command interfaces for migrations.

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

from ...datastructures import sdict
from .base import Schema, Column
from .helpers import make_migration_id, to_tuple
from .operations import MigrationOp, UpgradeOps, DowngradeOps
from .scripts import ScriptDir


class Command(object):
    def __init__(self, app, dals):
        self.app = app
        self.envs = []
        self._load_envs(dals)

    def _load_envs(self, dals):
        for dal in dals:
            self.envs.append(
                sdict(
                    db=dal,
                    scriptdir=ScriptDir(
                        self.app, dal.config.migrations_folder)))

    def load_schema(self, ctx):
        ctx.db.define_models(Schema)
        with ctx.db.connection():
            self._ensure_schema_table_(ctx)
            self._load_current_revision_(ctx)

    def _ensure_schema_table_(self, ctx):
        # TODO -> has_table method in adapter, I don't like this "dirtness"
        try:
            ctx.db(ctx.db.Schema.id > 0).count()
        except Exception:
            ctx.db.rollback()
            from .engine import Engine
            from .operations import CreateTableOp
            op = CreateTableOp.from_table(self._build_schema_metatable_(ctx))
            op.engine = Engine(ctx.db)
            op.run()
            ctx.db.commit()

    @staticmethod
    def _build_schema_metatable_(ctx):
        from .generation import MetaTable
        columns = []
        for field in list(ctx.db.Schema):
            columns.append(Column.from_field(field))
        return MetaTable(
            ctx.db.Schema._tablename,
            columns
        )

    @staticmethod
    def _load_current_revision_(ctx):
        revisions = ctx.db(ctx.db.Schema.id > 0).select()
        if not revisions:
            ctx._current_revision_ = []
        elif len(revisions) == 1:
            ctx._current_revision_ = [revisions[0].version]
        else:
            ctx._current_revision_ = [rev.version for rev in revisions]

    @staticmethod
    def _store_current_revision_(ctx, source, dest):
        logs = {
            'new': '> Adding revision %s to schema',
            'del': '> Removing revision %s from schema',
            'upd': '> Updating schema revision from %s to %s'}
        source = to_tuple(source)
        dest = to_tuple(dest)
        if source is None:
            print(logs['new'] % dest[0])
            ctx.db.Schema.insert(version=dest[0])
            ctx.db.commit()
            ctx._current_revision_ = [dest[0]]
            return
        if dest is None:
            print(logs['del'] % source[0])
            ctx.db(ctx.db.Schema.version == source[0]).delete()
            ctx.db.commit()
            ctx._current_revision_ = []
            return
        if len(source) > 1:
            if len(source) > 2:
                ctx.db(
                    ctx.db.Schema.version.belongs(
                        source[1:])).delete()
                print(logs['del'] % source[1:])
            else:
                ctx.db(
                    ctx.db.Schema.version == source[1]).delete()
                print(logs['del'] % source[1])
            ctx.db(ctx.db.Schema.version == source[0]).update(
                version=dest[0]
            )
            print(logs['upd'] % (source[0], dest[0]))
            ctx._current_revision_ = [dest[0]]
        else:
            if list(source) != ctx._current_revision_:
                ctx.db.Schema.insert(version=dest[0])
                print(logs['new'] % dest[0])
                ctx._current_revision_.append(dest[0])
            else:
                ctx.db(
                    ctx.db.Schema.version == source[0]
                ).update(
                    version=dest[0]
                )
                print(logs['upd'] % (source[0], dest[0]))
                ctx._current_revision_ = [dest[0]]
        ctx.db.commit()

    @staticmethod
    def _generate_migration_script(ctx, migration, head):
        from .generation import Renderer
        upgrades, downgrades = Renderer.render_migration(migration)
        ctx.scriptdir.generate_revision(
            migration.rev_id, migration.message, head, upgrades=upgrades,
            downgrades=downgrades
        )

    def generate(self, message, head):
        from .generation import Generator
        for ctx in self.envs:
            upgrade_ops = Generator.generate_from(ctx.db, ctx.scriptdir, head)
            revid = make_migration_id()
            migration = MigrationOp(
                revid, upgrade_ops, upgrade_ops.reverse(), message)
            self._generate_migration_script(ctx, migration, head)
            print("> Generated migration for revision %s" % revid)

    def new(self, message, head):
        for ctx in self.envs:
            source_rev = ctx.scriptdir.get_revision(head)
            revid = make_migration_id()
            migration = MigrationOp(
                revid, UpgradeOps(), DowngradeOps(), message
            )
            self._generate_migration_script(
                ctx, migration, source_rev.revision)
            print("> Created new migration with revision %s" % revid)

    def history(self, base, head, verbose):
        for ctx in self.envs:
            print("> Migrations history")
            lines = []
            for sc in ctx.scriptdir.walk_revisions(
                    base=base or "base",
                    head=head or "heads"):
                lines.append(
                    sc.cmd_format(
                        verbose=verbose, include_doc=True, include_parents=True
                    )
                )
            for line in lines:
                print(line)
            if not lines:
                print("No migrations for the selected application.")

    def status(self, verbose):
        for ctx in self.envs:
            self.load_schema(ctx)
            print("> Current revision(s) for %s" % ctx.db._uri)
            lines = []
            for rev in ctx.scriptdir.get_revisions(ctx._current_revision_):
                lines.append(rev.cmd_format(verbose))
            for line in lines:
                print(line)
            if not lines:
                print("No revision state found on the schema.")

    def up(self, rev_id):
        for ctx in self.envs:
            self.load_schema(ctx)
            start_point = ctx._current_revision_
            revisions = ctx.scriptdir.get_upgrade_revs(
                rev_id, start_point)
            print("> Performing upgrades against %s" % ctx.db._uri)
            with ctx.db.connection():
                for revision in revisions:
                    print("> Performing upgrade: %s" % revision)
                    migration = revision.migration_class(self.app, ctx.db)
                    try:
                        migration.up()
                        ctx.db.commit()
                        self._store_current_revision_(
                            ctx, migration.revises, migration.revision)
                        print(
                            "> Succesfully upgraded to revision %s: %s" %
                            (revision.revision, revision.doc)
                        )
                    except Exception:
                        ctx.db.rollback()
                        print("[ERROR] failed upgrading to %s" % revision)
                        raise

    def down(self, rev_id):
        for ctx in self.envs:
            self.load_schema(ctx)
            start_point = ctx._current_revision_
            revisions = ctx.scriptdir.get_downgrade_revs(
                rev_id, start_point)
            print("> Performing downgrades against %s" % ctx.db._uri)
            with ctx.db.connection():
                for revision in revisions:
                    print("> Performing downgrade: %s" % revision)
                    migration = revision.migration_class(self.app, ctx.db)
                    try:
                        migration.down()
                        ctx.db.commit()
                        self._store_current_revision_(
                            ctx, migration.revision, migration.revises)
                        print(
                            "> Succesfully downgraded from revision %s: %s" %
                            (revision.revision, revision.doc)
                        )
                    except Exception:
                        ctx.db.rollback()
                        print("[ERROR] failed downgrading from %s" % revision)
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
