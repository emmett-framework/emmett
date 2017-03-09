# -*- coding: utf-8 -*-
"""
    weppy.orm.migrations.revisions
    ------------------------------

    Provides revisions logic for migrations.

    :copyright: (c) 2014-2017 by Giovanni Barillari

    Based on the code of Alembic (https://bitbucket.org/zzzeek/alembic)
    :copyright: (c) 2009-2015 by Michael Bayer

    :license: BSD, see LICENSE for more details.
"""

from collections import deque
from ...datastructures import OrderedSet
from ...utils import cachedprop
from .helpers import to_tuple, tuple_or_value, dedupe_tuple
from .exceptions import (
    RevisionError, RangeNotAncestorError, ResolutionError, MultipleHeads
)


class Revision(object):
    nextrev = frozenset()
    _all_nextrev = frozenset()
    revision = None
    down_revision = None
    #dependencies = None
    #branch_labels = None

    def __init__(self, revision, down_revision,
                 dependencies=None, branch_labels=None):
        self.revision = revision
        self.down_revision = tuple_or_value(down_revision)
        #self.dependencies = tuple_or_value(dependencies)
        #self._resolved_dependencies = ()
        #self._orig_branch_labels = to_tuple(branch_labels, default=())
        #self.branch_labels = set(self._orig_branch_labels)

    def __repr__(self):
        args = [
            repr(self.revision),
            repr(self.down_revision)
        ]
        # if self.dependencies:
        #     args.append("dependencies=%r" % self.dependencies)
        # if self.branch_labels:
        #     args.append("branch_labels=%r" % self.branch_labels)
        return "%s(%s)" % (
            self.__class__.__name__,
            ", ".join(args)
        )

    def add_nextrev(self, revision):
        self._all_nextrev = self._all_nextrev.union([revision.revision])
        if self.revision in revision._versioned_down_revisions:
            self.nextrev = self.nextrev.union([revision.revision])

    @property
    def _all_down_revisions(self):
        return to_tuple(self.down_revision, default=())
        #+ self._resolved_dependencies

    @property
    def _versioned_down_revisions(self):
        return to_tuple(self.down_revision, default=())

    @property
    def is_head(self):
        return not bool(self.nextrev)

    @property
    def _is_real_head(self):
        return not bool(self._all_nextrev)

    @property
    def is_base(self):
        return self.down_revision is None

    # @property
    # def _is_real_base(self):
    #     return self.down_revision is None and self.dependencies is None

    @property
    def is_branch_point(self):
        return len(self.nextrev) > 1

    @property
    def _is_real_branch_point(self):
        return len(self._all_nextrev) > 1

    @property
    def is_merge_point(self):
        return len(self._versioned_down_revisions) > 1


class RevisionsMap(object):
    def __init__(self, app, generator):
        self.app = app
        self._generator = generator

    @cachedprop
    def _revision_map(self):
        rmap = {}

        heads = OrderedSet()
        _real_heads = OrderedSet()
        self.bases = ()
        self._real_bases = ()

        #has_branch_labels = set()
        #has_depends_on = set()
        for revision in self._generator():

            if revision.revision in rmap:
                self.app.log.warn(
                    "Revision %s is present more than once" % revision.revision
                )
            rmap[revision.revision] = revision
            # if revision.branch_labels:
            #     has_branch_labels.add(revision)
            # if revision.dependencies:
            #     has_depends_on.add(revision)
            heads.add(revision.revision)
            _real_heads.add(revision.revision)
            if revision.is_base:
                self.bases += (revision.revision, )
                self._real_bases += (revision.revision, )
            #if revision._is_real_base:
            #    self._real_bases += (revision.revision, )

        # for revision in has_branch_labels:
        #     self._map_branch_labels(revision, rmap)

        # for revision in has_depends_on:
        #     self._add_depends_on(revision, rmap)

        for rev in rmap.values():
            for downrev in rev._all_down_revisions:
                if downrev not in rmap:
                    self.app.log.warn(
                        "Revision %s referenced from %s is not present" %
                        (downrev, rev))
                down_revision = rmap[downrev]
                down_revision.add_nextrev(rev)
                if downrev in rev._versioned_down_revisions:
                    heads.discard(downrev)
                _real_heads.discard(downrev)

        rmap[None] = rmap[()] = None
        self.heads = tuple(heads)
        self._real_heads = tuple(_real_heads)

        # for revision in has_branch_labels:
        #     self._add_branches(revision, rmap, map_branch_labels=False)
        return rmap

    @cachedprop
    def heads(self):
        self._revision_map
        return self.heads

    @cachedprop
    def bases(self):
        self._revision_map
        return self.bases

    @cachedprop
    def _real_heads(self):
        self._revision_map
        return self._real_heads

    @cachedprop
    def _real_bases(self):
        self._revision_map
        return self._real_bases

    def get_current_head(self):
        current_heads = self.heads
        if len(current_heads) > 1:
            raise MultipleHeads(current_heads, "head")
        if current_heads:
            return current_heads[0]
        else:
            return None

    def _resolve_revision_number(self, rid):
        self._revision_map
        if rid == 'heads':
            return self._real_heads
        elif rid == 'head':
            current_head = self.get_current_head()
            if current_head:
                return (current_head, )
            return ()
        elif rid == 'base' or rid is None:
            return ()
        else:
            return to_tuple(rid, default=None)

    def _revision_for_ident(self, resolved_id):
        try:
            revision = self._revision_map[resolved_id]
        except KeyError:
            # do a partial lookup
            revs = [x for x in self._revision_map
                    if x and x.startswith(resolved_id)]
            if not revs:
                raise ResolutionError(
                    "No such revision or branch '%s'" % resolved_id,
                    resolved_id)
            elif len(revs) > 1:
                raise ResolutionError(
                    "Multiple revisions start "
                    "with '%s': %s..." % (
                        resolved_id,
                        ", ".join("'%s'" % r for r in revs[0:3])
                    ), resolved_id)
            else:
                revision = self._revision_map[revs[0]]
        return revision

    def get_revision(self, rid):
        resolved_id = self._resolve_revision_number(rid)
        if len(resolved_id) > 1:
            raise MultipleHeads(resolved_id, rid)
        elif resolved_id:
            resolved_id = resolved_id[0]
        return self._revision_for_ident(resolved_id)

    def get_revisions(self, rid):
        #: return revision instances with the given rev id or identifiers
        if isinstance(rid, (list, tuple, set, frozenset)):
            return sum([self.get_revisions(id_elem) for id_elem in rid], ())
        else:
            resolved_id = self._resolve_revision_number(rid)
            return tuple(
                self._revision_for_ident(rev_id) for rev_id in resolved_id)

    def add_revision(self, revision, _replace=False):
        map_ = self._revision_map
        if not _replace and revision.revision in map_:
            self.app.log.warn(
                "Revision %s is present more than once" % revision.revision)
        elif _replace and revision.revision not in map_:
            raise Exception("revision %s not in map" % revision.revision)

        map_[revision.revision] = revision

        if revision.is_base:
            self.bases += (revision.revision, )
            self._real_bases += (revision.revision, )
        # if revision._is_real_base:
        #     self._real_bases += (revision.revision, )
        for downrev in revision._all_down_revisions:
            if downrev not in map_:
                self.app.log.warn(
                    "Revision %s referenced from %s is not present"
                    % (downrev, revision)
                )
            map_[downrev].add_nextrev(revision)
        if revision._is_real_head:
            self._real_heads = tuple(
                head for head in self._real_heads
                if head not in
                set(revision._all_down_revisions).union([revision.revision])
            ) + (revision.revision,)
        if revision.is_head:
            self.heads = tuple(
                head for head in self.heads
                if head not in
                set(revision._versioned_down_revisions).union(
                    [revision.revision])
            ) + (revision.revision,)

    def iterate_revisions(self, upper, lower, implicit_base=False,
                          inclusive=False):
        #: iterate through script revisions, starting at the given upper
        #  revision identifier and ending at the lower.
        return self._iterate_revisions(
            upper, lower, inclusive=inclusive, implicit_base=implicit_base)

    def _get_ancestor_nodes(self, targets, map_=None, check=False):
        fn = lambda rev: rev._versioned_down_revisions

        return self._iterate_related_revisions(
            fn, targets, map_=map_, check=check
        )

    def _get_descendant_nodes(self, targets, map_=None, check=False):
        fn = lambda rev: rev.nextrev

        return self._iterate_related_revisions(
            fn, targets, map_=map_, check=check
        )

    def _iterate_related_revisions(self, fn, targets, map_, check=False):
        if map_ is None:
            map_ = self._revision_map

        seen = set()
        todo = deque()
        for target in targets:

            todo.append(target)
            if check:
                per_target = set()

            while todo:
                rev = todo.pop()
                if check:
                    per_target.add(rev)

                if rev in seen:
                    continue
                seen.add(rev)
                todo.extend(
                    map_[rev_id] for rev_id in fn(rev))
                yield rev
            if check and per_target.intersection(targets).difference([target]):
                raise RevisionError(
                    "Requested revision %s overlaps with "
                    "other requested revisions" % target.revision)

    def _iterate_revisions(self, upper, lower, inclusive=True,
                           implicit_base=False):
        #: iterate revisions from upper to lower.
        requested_lowers = self.get_revisions(lower)
        uppers = dedupe_tuple(self.get_revisions(upper))

        if not uppers and not requested_lowers:
            raise StopIteration()

        upper_ancestors = set(self._get_ancestor_nodes(uppers, check=True))

        if implicit_base and requested_lowers:
            lower_ancestors = set(
                self._get_ancestor_nodes(requested_lowers)
            )
            lower_descendants = set(
                self._get_descendant_nodes(requested_lowers)
            )
            base_lowers = set()
            candidate_lowers = upper_ancestors.\
                difference(lower_ancestors).\
                difference(lower_descendants)
            for rev in candidate_lowers:
                for downrev in rev._all_down_revisions:
                    if self._revision_map[downrev] in candidate_lowers:
                        break
                else:
                    base_lowers.add(rev)
            lowers = base_lowers.union(requested_lowers)
        elif implicit_base:
            base_lowers = set(self.get_revisions(self._real_bases))
            lowers = base_lowers.union(requested_lowers)
        elif not requested_lowers:
            lowers = set(self.get_revisions(self._real_bases))
        else:
            lowers = requested_lowers

        # represents all nodes we will produce
        total_space = set(
            rev.revision for rev in upper_ancestors).intersection(
            rev.revision for rev
            in self._get_descendant_nodes(lowers, check=True)
        )

        if not total_space:
            raise RangeNotAncestorError(lower, upper)

        # organize branch points to be consumed separately from
        # member nodes
        branch_todo = set(
            rev for rev in
            (self._revision_map[rev] for rev in total_space)
            if rev._is_real_branch_point and
            len(total_space.intersection(rev._all_nextrev)) > 1
        )

        # it's not possible for any "uppers" to be in branch_todo,
        # because the ._all_nextrev of those nodes is not in total_space
        #assert not branch_todo.intersection(uppers)

        todo = deque(
            r for r in uppers if r.revision in total_space)

        # iterate for total_space being emptied out
        total_space_modified = True
        while total_space:

            if not total_space_modified:
                raise RevisionError(
                    "Dependency resolution failed; iteration can't proceed")
            total_space_modified = False
            # when everything non-branch pending is consumed,
            # add to the todo any branch nodes that have no
            # descendants left in the queue
            if not todo:
                todo.extendleft(
                    sorted(
                        (
                            rev for rev in branch_todo
                            if not rev._all_nextrev.intersection(total_space)
                        ),
                        # favor "revisioned" branch points before
                        # dependent ones
                        key=lambda rev: 0 if rev.is_branch_point else 1
                    )
                )
                branch_todo.difference_update(todo)
            # iterate nodes that are in the immediate todo
            while todo:
                rev = todo.popleft()
                total_space.remove(rev.revision)
                total_space_modified = True

                # do depth first for elements within branches,
                # don't consume any actual branch nodes
                todo.extendleft([
                    self._revision_map[downrev]
                    for downrev in reversed(rev._all_down_revisions)
                    if self._revision_map[downrev] not in branch_todo and
                    downrev in total_space])

                if not inclusive and rev in requested_lowers:
                    continue
                yield rev

        assert not branch_todo
