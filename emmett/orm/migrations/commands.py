# -*- coding: utf-8 -*-
"""
    emmett.orm.migrations.commands
    ------------------------------

    Provides command interfaces for migrations.

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

from __future__ import annotations

from typing import Any, List

import click

from ...datastructures import sdict
from .base import Database, Schema, Column
from .helpers import DryRunDatabase, make_migration_id, to_tuple
from .operations import MigrationOp, UpgradeOps, DowngradeOps
from .scripts import ScriptDir


class Command:
    def __init__(self, app: Any, dals: List[Database]):
        self.app = app
        self.envs: List[sdict] = []
        self._load_envs(dals)

    def _load_envs(self, dals):
        for dal in dals:
            self.envs.append(
                sdict(
                    db=dal,
                    scriptdir=ScriptDir(
                        self.app, dal.config.migrations_folder
                    )
                )
            )

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
    def _log_store_new(revid):
        click.echo(
            " ".join([
                "> Adding revision",
                click.style(revid, fg="cyan", bold=True),
                "to schema"
            ])
        )

    @staticmethod
    def _log_store_del(revid):
        click.echo(
            " ".join([
                "> Removing revision",
                click.style(revid, fg="cyan", bold=True),
                "from schema"
            ])
        )

    @staticmethod
    def _log_store_upd(revid_src, revid_dst):
        click.echo(
            " ".join([
                "> Updating schema revision from",
                click.style(revid_src, fg="cyan", bold=True),
                "to",
                click.style(revid_dst, fg="cyan", bold=True),
            ])
        )

    @staticmethod
    def _log_dry_run(msg):
        click.secho(msg, fg='yellow')

    def _store_current_revision_(self, ctx, source, dest):
        _store_logs = {
            'new': self._log_store_new,
            'del': self._log_store_del,
            'upd': self._log_store_upd
        }
        source = to_tuple(source)
        dest = to_tuple(dest)
        if not source and dest:
            _store_logs['new'](dest[0])
            ctx.db.Schema.insert(version=dest[0])
            ctx.db.commit()
            ctx._current_revision_ = [dest[0]]
            return
        if not dest and source:
            _store_logs['del'](source[0])
            ctx.db(ctx.db.Schema.version == source[0]).delete()
            ctx.db.commit()
            ctx._current_revision_ = []
            return
        if len(source) > 1:
            if len(source) > 2:
                ctx.db(
                    ctx.db.Schema.version.belongs(
                        source[1:])).delete()
                _store_logs['del'](source[1:])
            else:
                ctx.db(
                    ctx.db.Schema.version == source[1]).delete()
                _store_logs['del'](source[1])
            ctx.db(ctx.db.Schema.version == source[0]).update(
                version=dest[0]
            )
            _store_logs['upd'](source[0], dest[0])
            ctx._current_revision_ = [dest[0]]
        else:
            if list(source) != ctx._current_revision_:
                ctx.db.Schema.insert(version=dest[0])
                _store_logs['new'](dest[0])
                ctx._current_revision_.append(dest[0])
            else:
                ctx.db(
                    ctx.db.Schema.version == source[0]
                ).update(
                    version=dest[0]
                )
                _store_logs['upd'](source[0], dest[0])
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
                revid, upgrade_ops, upgrade_ops.reverse(), message
            )
            self._generate_migration_script(ctx, migration, head)
            click.echo(
                " ".join([
                    "> Generated migration for revision",
                    click.style(revid, fg="cyan", bold=True)
                ])
            )

    def new(self, message, head):
        for ctx in self.envs:
            source_rev = ctx.scriptdir.get_revision(head)
            revid = make_migration_id()
            migration = MigrationOp(
                revid, UpgradeOps(), DowngradeOps(), message
            )
            self._generate_migration_script(
                ctx, migration, source_rev.revision
            )
            click.echo(
                " ".join([
                    "> Created new migration for revision",
                    click.style(revid, fg="cyan", bold=True)
                ])
            )

    def history(self, base, head, verbose):
        for ctx in self.envs:
            click.echo("> Migrations history:")
            lines = []
            for sc in ctx.scriptdir.walk_revisions(
                base=base or "base",
                head=head or "heads"
            ):
                lines.append(
                    sc.cmd_format(
                        verbose=verbose, include_doc=True, include_parents=True
                    )
                )
            for line in lines:
                click.echo(line)
            if not lines:
                click.secho(
                    "No migrations for the selected application.", fg="yellow"
                )

    def status(self, verbose):
        for ctx in self.envs:
            self.load_schema(ctx)
            click.echo(
                " ".join([
                    "> Current revision(s) for",
                    click.style(ctx.db._uri, bold=True)
                ])
            )
            lines = []
            for rev in ctx.scriptdir.get_revisions(ctx._current_revision_):
                lines.append(rev.cmd_format(verbose))
            for line in lines:
                click.echo(line)
            if not lines:
                click.secho(
                    "No revision state found on the schema.", fg="yellow"
                )

    def up(self, rev_id, dry_run=False):
        log_verb = "Previewing" if dry_run else "Performing"
        for ctx in self.envs:
            self.load_schema(ctx)
            start_point = ctx._current_revision_
            revisions = ctx.scriptdir.get_upgrade_revs(
                rev_id, start_point
            )
            click.echo(
                " ".join([
                    f"> {log_verb} upgrades against",
                    click.style(ctx.db._uri, bold=True)
                ])
            )
            db = (
                DryRunDatabase(ctx.db, self._log_dry_run) if dry_run else
                ctx.db
            )
            with db.connection():
                for revision in revisions:
                    click.echo(
                        " ".join([
                            f"> {log_verb} upgrade:",
                            click.style(str(revision), fg="cyan", bold=True)
                        ])
                    )
                    migration = revision.migration_class(self.app, db)
                    try:
                        migration.up()
                        db.commit()
                        if dry_run:
                            continue
                        self._store_current_revision_(
                            ctx, migration.revises, migration.revision
                        )
                        click.echo(
                            "".join([
                                click.style(
                                    "> Succesfully upgraded to revision ",
                                    fg="green"
                                ),
                                click.style(
                                    revision.revision, fg="cyan", bold=True
                                ),
                                click.style(f": {revision.doc}", fg="green")
                            ])
                        )
                    except Exception:
                        db.rollback()
                        click.echo(
                            " ".join([
                                click.style("> Failed upgrading to", fg="red"),
                                click.style(
                                    revision.revision, fg="red", bold=True
                                ),
                            ])
                        )
                        raise

    def down(self, rev_id, dry_run=False):
        log_verb = "Previewing" if dry_run else "Performing"
        for ctx in self.envs:
            self.load_schema(ctx)
            start_point = ctx._current_revision_
            revisions = ctx.scriptdir.get_downgrade_revs(
                rev_id, start_point)
            click.echo(
                " ".join([
                    f"> {log_verb} downgrades against",
                    click.style(ctx.db._uri, bold=True)
                ])
            )
            db = (
                DryRunDatabase(ctx.db, self._log_dry_run) if dry_run else
                ctx.db
            )
            with db.connection():
                for revision in revisions:
                    click.echo(
                        " ".join([
                            f"> {log_verb} downgrade:",
                            click.style(str(revision), fg="cyan", bold=True)
                        ])
                    )
                    migration = revision.migration_class(self.app, db)
                    try:
                        migration.down()
                        db.commit()
                        if dry_run:
                            continue
                        self._store_current_revision_(
                            ctx, migration.revision, migration.revises
                        )
                        click.echo(
                            "".join([
                                click.style(
                                    "> Succesfully downgraded from revision ",
                                    fg="green"
                                ),
                                click.style(
                                    revision.revision, fg="cyan", bold=True
                                ),
                                click.style(f": {revision.doc}", fg="green")
                            ])
                        )
                    except Exception:
                        db.rollback()
                        click.echo(
                            " ".join([
                                click.style(
                                    "> Failed downgrading from", fg="red"
                                ),
                                click.style(
                                    revision.revision, fg="red", bold=True
                                ),
                            ])
                        )
                        raise

    def set(self, rev_id, auto_confirm=False):
        for ctx in self.envs:
            self.load_schema(ctx)
            current_revision = ctx._current_revision_
            target_revision = ctx.scriptdir.get_revision(rev_id)
            if not target_revision:
                click.secho("> No matching revision found", fg="red")
                return
            click.echo(
                " ".join([
                    click.style("> Setting revision to", fg="yellow"),
                    click.style(target_revision.revision, bold=True, fg="yellow"),
                    click.style("against", fg="yellow"),
                    click.style(ctx.db._uri, bold=True, fg="yellow")
                ])
            )
            if not auto_confirm:
                if not click.confirm("Do you want to continue?"):
                    click.echo("Aborting")
                    return
            with ctx.db.connection():
                self._store_current_revision_(
                    ctx, current_revision, target_revision.revision
                )
                click.echo(
                    "".join([
                        click.style(
                            "> Succesfully set revision to ",
                            fg="green"
                        ),
                        click.style(
                            target_revision.revision, fg="cyan", bold=True
                        ),
                        click.style(f": {target_revision.doc}", fg="green")
                    ])
                )


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


def up(app, dals, revision, dry_run):
    Command(app, dals).up(revision, dry_run)


def down(app, dals, revision, dry_run):
    Command(app, dals).down(revision, dry_run)


def set_revision(app, dals, revision, auto_confirm):
    Command(app, dals).set(revision, auto_confirm)
