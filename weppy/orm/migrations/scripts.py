# -*- coding: utf-8 -*-
"""
    weppy.orm.migrations.scripts
    ----------------------------

    Provides scripts interface for migrations.

    :copyright: (c) 2014-2017 by Giovanni Barillari

    Based on the code of Alembic (https://bitbucket.org/zzzeek/alembic)
    :copyright: (c) 2009-2015 by Michael Bayer

    :license: BSD, see LICENSE for more details.
"""

import os
import re
import sys
from contextlib import contextmanager
from datetime import datetime
from ..._compat import itervalues, to_bytes, string_types
from .base import Migration
from .exceptions import (
    RangeNotAncestorError, MultipleHeads, ResolutionError, RevisionError
)
from .revisions import Revision, RevisionsMap
from .helpers import tuple_rev_as_scalar, render_template, format_with_comma


class ScriptDir(object):
    _slug_re = re.compile(r'\w+')
    _default_file_template = "%(rev)s_%(slug)s"

    def __init__(self, app):
        self.app = app
        self.path = os.path.join(app.root_path, "migrations")
        if not os.path.exists(self.path):
            os.mkdir(self.path)
        #self.cwd = os.path.join(os.path.dirname(__file__), 'migration.tmpl')
        self.cwd = os.path.dirname(__file__)
        self.file_template = self.app.config.migrations.file_template or \
            self._default_file_template
        self.truncate_slug_length = \
            self.app.config.migrations.filename_len or 40
        self.revision_map = RevisionsMap(self.app, self._load_revisions)

    def _load_revisions(self):
        sys.path.insert(0, self.path)
        for rev_file in os.listdir(os.path.abspath(self.path)):
            script = Script._from_filename(self, rev_file)
            if script is None:
                continue
            yield script

    @contextmanager
    def _catch_revision_errors(
            self,
            ancestor=None, multiple_heads=None, start=None, end=None,
            resolution=None):
        try:
            yield
        except RangeNotAncestorError as rna:
            if start is None:
                start = rna.lower
            if end is None:
                end = rna.upper
            if not ancestor:
                ancestor = (
                    "Requested range %(start)s:%(end)s does not refer to "
                    "ancestor/descendant revisions along the same branch"
                )
            ancestor = ancestor % {"start": start, "end": end}
            raise Exception(ancestor)
        except MultipleHeads as mh:
            if not multiple_heads:
                multiple_heads = (
                    "Multiple head revisions are present for given "
                    "argument '%(head_arg)s'; please "
                    "specify a specific target revision, "
                    "'<branchname>@%(head_arg)s' to "
                    "narrow to a specific head, or 'heads' for all heads")
            multiple_heads = multiple_heads % {
                "head_arg": end or mh.argument,
                "heads": str(mh.heads)
            }
            raise Exception(multiple_heads)
        except ResolutionError as re:
            if resolution is None:
                resolution = "Can't locate revision identified by '%s'" % (
                    re.argument
                )
            raise Exception(resolution)
        except RevisionError as err:
            raise Exception(err.args[0])

    def walk_revisions(self, base="base", head="heads"):
        with self._catch_revision_errors(start=base, end=head):
            for rev in self.revision_map.iterate_revisions(
                    head, base, inclusive=True):
                yield rev

    def get_revision(self, revid):
        with self._catch_revision_errors():
            return self.revision_map.get_revision(revid)

    def get_revisions(self, revid):
        with self._catch_revision_errors():
            return self.revision_map.get_revisions(revid)

    def get_upgrade_revs(self, destination, current_rev):
        with self._catch_revision_errors(
                ancestor="Destination %(end)s is not a valid upgrade "
                "target from current head(s)", end=destination):
            revs = self.revision_map.iterate_revisions(
                destination, current_rev, implicit_base=True)
            return reversed(list(revs))

    def get_downgrade_revs(self, destination, current_rev):
        with self._catch_revision_errors(
                ancestor="Destination %(end)s is not a valid downgrade "
                "target from current head(s)", end=destination):
            revs = self.revision_map.iterate_revisions(
                current_rev, destination)
            return list(revs)

    def _rev_filename(self, revid, message, creation_date):
        slug = "_".join(self._slug_re.findall(message or "")).lower()
        if len(slug) > self.truncate_slug_length:
            slug = slug[:self.truncate_slug_length].rsplit('_', 1)[0] + '_'
        filename = "%s.py" % (
            self.file_template % {
                'rev': revid,
                'slug': slug,
                'year': creation_date.year,
                'month': creation_date.month,
                'day': creation_date.day,
                'hour': creation_date.hour,
                'minute': creation_date.minute,
                'second': creation_date.second
            }
        )
        return filename

    def _generate_template(self, filename, ctx):
        rendered = render_template(self.cwd, 'migration.tmpl', ctx)
        with open(os.path.join(self.path, filename), 'wb') as f:
            f.write(to_bytes(rendered))

    def generate_revision(self, revid, message, head=None, splice=False, **kw):
        """Generate a new revision file.

        This runs the templater, and creates a new file.

        :param revid: String revision id.
        :param message: the revision message.
        :param head: the head revision to generate against. Defaults
         to the current "head" if no branches are present, else raises
         an exception.
        :param splice: if True, allow the "head" version to not be an
         actual head; otherwise, the selected head must be a head
         (e.g. endpoint) revision.
        """
        if head is None:
            head = "head"

        with self._catch_revision_errors(multiple_heads=(
            "Multiple heads are present; please specify the head "
            "revision on which the new revision should be based, "
            "or perform a merge."
        )):
            heads = self.revision_map.get_revisions(head)

        if len(set(heads)) != len(heads):
            raise Exception("Duplicate head revisions specified")

        creation_date = datetime.now()

        rev_filename = self._rev_filename(revid, message, creation_date)

        if not splice:
            for head in heads:
                if head is not None and not head.is_head:
                    raise Exception(
                        "Revision %s is not a head revision; please specify "
                        "--splice to create a new branch from this revision"
                        % head.revision)

        down_migration = tuple(
            h.revision if h is not None else None for h in heads)

        down_migration_var = tuple_rev_as_scalar(down_migration)
        if isinstance(down_migration_var, string_types):
            down_migration_var = "%r" % down_migration_var
        else:
            down_migration_var = str(down_migration_var)

        template_ctx = dict(
            up_migration=revid,
            down_migration=down_migration_var,
            creation_date=creation_date,
            down_migration_str=", ".join(r for r in down_migration),
            message=message if message is not None else ("empty message"),
            upgrades=kw.get('upgrades', ['pass']),
            downgrades=kw.get('downgrades', ['pass'])
        )
        self._generate_template(rev_filename, template_ctx)

        script = Script._from_filename(self, rev_filename)
        self.revision_map.add_revision(script)
        return script


class Script(Revision):
    _only_source_rev_file = re.compile(r'(?!__init__)(.*\.py)$')
    migration_class = None
    path = None

    def __init__(self, module, migration_class, path):
        self.module = module
        self.migration_class = migration_class
        self.path = path
        super(Script, self).__init__(
            self.migration_class.revision,
            self.migration_class.revises
        )

    @property
    def doc(self):
        return re.split("\n\n", self.longdoc)[0]

    @property
    def longdoc(self):
        doc = self.module.__doc__
        return doc.strip() if doc else ""

    @property
    def log_entry(self):
        entry = "Rev: %s%s%s%s\n" % (
            self.revision,
            " (head)" if self.is_head else "",
            " (branchpoint)" if self.is_branch_point else "",
            " (mergepoint)" if self.is_merge_point else "",
        )
        if self.is_merge_point:
            entry += "Merges: %s\n" % (self._format_down_revision(), )
        else:
            entry += "Parent: %s\n" % (self._format_down_revision(), )

        if self.is_branch_point:
            entry += "Branches into: %s\n" % (
                format_with_comma(self.nextrev))

        entry += "Path: %s\n" % (self.path,)

        entry += "\n%s\n" % (
            "\n".join(
                "    %s" % para
                for para in self.longdoc.splitlines()
            )
        )
        return entry

    def __str__(self):
        return "%s -> %s%s%s%s, %s" % (
            self._format_down_revision(),
            self.revision,
            " (head)" if self.is_head else "",
            " (branchpoint)" if self.is_branch_point else "",
            " (mergepoint)" if self.is_merge_point else "",
            self.doc)

    def _head_only(
            self, include_doc=False,
            include_parents=False, tree_indicators=True,
            head_indicators=True):
        text = self.revision
        if include_parents:
            text = "%s -> %s" % (
                self._format_down_revision(), text)
        if head_indicators or tree_indicators:
            text += "%s%s" % (
                " (head)" if self._is_real_head else "",
                " (effective head)" if self.is_head and
                    not self._is_real_head else ""
            )
        if tree_indicators:
            text += "%s%s" % (
                " (branchpoint)" if self.is_branch_point else "",
                " (mergepoint)" if self.is_merge_point else "",
            )
        if include_doc:
            text += ", %s" % self.doc
        return text

    def cmd_format(
        self,
            verbose,
            include_doc=False,
            include_parents=False, tree_indicators=True):
        if verbose:
            return self.log_entry
        else:
            return self._head_only(
                include_doc,
                include_parents, tree_indicators)

    def _format_down_revision(self):
        if not self.down_revision:
            return "<base>"
        else:
            return format_with_comma(self._versioned_down_revisions)

    @classmethod
    def _from_filename(cls, scriptdir, filename):
        py_match = cls._only_source_rev_file.match(filename)
        if not py_match:
            return None
        py_filename = py_match.group(1)
        py_module = py_filename.split('.py')[0]
        __import__(py_module)
        module = sys.modules[py_module]
        migration_class = getattr(module, 'Migration', None)
        if migration_class is None:
            for v in itervalues(module.__dict__):
                if isinstance(v, Migration):
                    migration_class = v
                    break
        return Script(
            module, migration_class, os.path.join(scriptdir.path, filename))
