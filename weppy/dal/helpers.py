# -*- coding: utf-8 -*-
"""
    weppy.dal.helpers
    -----------------

    Provides helpers for dal.

    :copyright: (c) 2014-2016 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

import re
import time
from pydal._globals import THREAD_LOCAL
from pydal.objects import Rows, Query
from pydal.helpers.classes import Reference as _IDReference, ExecutionHandler
from ..utils import cachedprop
from .base import Set, LazySet, Field


class Reference(object):
    def __init__(self, *args):
        self.reference = [arg for arg in args]
        self.refobj[id(self)] = self

    @property
    def refobj(self):
        return {}


class RelationBuilder(object):
    def __init__(self, ref, model):
        self.ref = ref
        self.model = model

    def _make_refid(self, row):
        return row.id if row is not None else self.model.id

    def _many_elements(self, row=None):
        rid = self._make_refid(row)
        field = self.model.db[self.ref['model']][self.ref['field']]
        return field, rid

    def _patch_query_with_scope(self, ref, query, model_name=None):
        mname = model_name or ref['model']
        if ref['scope'] is not None:
            ref_model = self.model.db[mname]._model_
            scope = ref_model._scopes_[ref['scope']].f
            query = query & scope(ref_model)
        if ref['where'] is not None:
            ref_model = self.model.db[mname]._model_
            query = query & ref['where'](ref_model)
        return query

    def _get_belongs(self, modelname, value):
        return self.model.db[modelname]._model_._belongs_ref_.get(value)

    def belongs_query(self):
        return (self.model.table[self.ref[1]] == self.model.db[self.ref[0]].id)

    def many_query(self, row=None):
        field, rid = self._many_elements(row)
        query = (field == rid)
        return self._patch_query_with_scope(self.ref, query)

    def many(self, row=None):
        scopes = []
        if self.ref['scope'] is not None:
            ref_model = self.model.db[self.ref['model']]._model_
            scope_m = ref_model._scopes_[self.ref['scope']].f
            scopes.append(lambda f=scope_m, m=ref_model: f(m))
        if self.ref['where'] is not None:
            ref_model = self.model.db[self.ref['model']]._model_
            scopes.append(lambda f=self.ref['where'], m=ref_model: f(m))
        return self._many_elements(row), scopes

    def via(self, row=None):
        db = self.model.db
        rid = self._make_refid(row)
        sname = self.model.__class__.__name__
        stack = []
        via = self.ref['via']
        midrel = self.model._hasmany_ref_[via]
        stack.append(self.ref)
        while midrel.get('via') is not None:
            stack.insert(0, midrel)
            midrel = self.model._hasmany_ref_[midrel['via']]
        query = self._patch_query_with_scope(
            midrel, db[midrel['model']][midrel['field']] == rid)
        sel_field = db[midrel['model']].ALL
        step_model = midrel['model']
        lbelongs = None
        lvia = None
        for via in stack:
            rname = via['field'] or via['name'][:-1]
            belongs = self._get_belongs(step_model, rname)
            if belongs:
                #: join table way
                lbelongs = step_model
                lvia = via
                _query = (db[belongs].id == db[step_model][rname])
                sel_field = db[belongs].ALL
                step_model = belongs
            else:
                #: shortcut mode
                lbelongs = None
                rname = via['field'] or via['name']
                many = db[step_model]._model_._hasmany_ref_[rname]
                _query = self._patch_query_with_scope(
                    many,
                    db[many['model']][many['field']] == db[step_model].id)
                sel_field = db[many['model']].ALL
                step_model = many['model']
            query = query & _query
        query = self._patch_query_with_scope(via, query, step_model)
        return query, sel_field, sname, rid, lbelongs, lvia


class ScopedRelationSet(object):
    @staticmethod
    def _get_fields_from_scope(scope):
        rv = {}
        if scope:
            query = scope()
            components = [query.second, query.first]
            current_kv = []
            while components:
                component = components.pop()
                if isinstance(component, Query):
                    components.append(component.second)
                    components.append(component.first)
                else:
                    if isinstance(component, Field):
                        current_kv.append(component)
                    else:
                        if current_kv:
                            current_kv.append(component)
                        else:
                            components.pop()
                if len(current_kv) > 1:
                    rv[current_kv[0].name] = current_kv[1]
                    current_kv = []
        return rv


class RelationSet(ScopedRelationSet, LazySet):
    def create(self, **kwargs):
        attributes = self._get_fields_from_scope(self._scope_)
        attributes.update(**kwargs)
        attributes[self.fieldname] = self.id
        return self._model_.create(
            **attributes
        )

    def select(self, *args, **kwargs):
        if kwargs.get('reload'):
            del kwargs['reload']
        return super(RelationSet, self).select(*args, **kwargs)


class HasOneSet(RelationSet):
    @cachedprop
    def _last_resultset(self):
        return self.select().first()

    def __call__(self, *args, **kwargs):
        if not args and not kwargs:
            return self._last_resultset
        return self.select(*args, **kwargs).first()


class HasOneWrap(object):
    def __init__(self, ref):
        self.ref = ref

    def __call__(self, model, row):
        rel_data = RelationBuilder(self.ref, model).many(row)
        return HasOneSet(*rel_data[0], scopes=rel_data[1])


class HasManySet(RelationSet):
    @cachedprop
    def _last_resultset(self):
        return self.select()

    def __call__(self, *args, **kwargs):
        if not args and not kwargs:
            return self._last_resultset
        return self.select(*args, **kwargs)

    def add(self, obj):
        attributes = self._get_fields_from_scope(self._scope_)
        attributes[self.fieldname] = self.id
        return self.db(
            self.db[self.tablename].id == obj.id
        ).validate_and_update(**attributes)

    def remove(self, obj):
        if self.db[self.tablename][self.fieldname]._isrefers:
            return self.db(
                self.db[self.tablename].id == obj.id).validate_and_update(
                **{self.fieldname: None}
            )
        else:
            return self.db(self.db[self.tablename].id == obj.id).delete()


class HasManyWrap(object):
    def __init__(self, ref):
        self.ref = ref

    def __call__(self, model, row):
        rel_data = RelationBuilder(self.ref, model).many(row)
        return HasManySet(*rel_data[0], scopes=rel_data[1])


class HasManyViaSet(ScopedRelationSet, Set):
    def __init__(self, db, query, rfield, modelname, rid, via, viadata,
                 **kwargs):
        self._rfield = rfield
        self._modelname = modelname
        self._rid = rid
        self._via = via
        self._viadata = viadata
        super(HasManyViaSet, self).__init__(
            db, query, model=db[modelname]._model_, **kwargs)
        self._via_error = \
            'Cannot %s elements to an has_many relation without a join table'

    @cachedprop
    def _last_resultset(self):
        return self.select(self._rfield)

    def __call__(self, *args, **kwargs):
        if not args:
            if not kwargs:
                return self._last_resultset
            args = [self._rfield]
        return self.select(*args, **kwargs)

    def select(self, *args, **kwargs):
        if kwargs.get('reload'):
            del kwargs['reload']
        return super(HasManyViaSet, self).select(*args, **kwargs)

    def _get_relation_fields(self):
        current_model = self.db[self._modelname]._model_
        self_field = current_model._hasmany_ref_[self._viadata['via']]['field']
        rel_field = self._viadata['field'] or self._viadata['name'][:-1]
        return self_field, rel_field

    def _fields_from_scope(self):
        current_model = self.db[self._modelname]._model_
        scope = current_model._hasmany_ref_[self._viadata['via']]['scope']
        if scope:
            join_model = self.db[
                current_model._hasmany_ref_[self._viadata['via']]['model']
            ]._model_
            scope_m = join_model._scopes_[scope].f
            scope = lambda f=scope_m, m=join_model: f(m)
            return self._get_fields_from_scope(scope)
        return {}

    def create(self, **kwargs):
        raise RuntimeError('Cannot create third objects for many relations')

    def add(self, obj, **kwargs):
        # works on join tables only!
        if self._via is None:
            raise RuntimeError(self._via_error % 'add')
        nrow = self._fields_from_scope()
        nrow.update(**kwargs)
        #: get belongs references
        self_field, rel_field = self._get_relation_fields()
        nrow[self_field] = self._rid
        nrow[rel_field] = obj.id
        #: validate and insert
        return self.db[self._via]._model_.create(nrow)

    def remove(self, obj):
        # works on join tables only!
        if self._via is None:
            raise RuntimeError(self._via_error % 'remove')
        #: get belongs references
        self_field, rel_field = self._get_relation_fields()
        #: delete
        return self.db(
            (self.db[self._via][self_field] == self._rid) &
            (self.db[self._via][rel_field] == obj.id)).delete()


class HasManyViaWrap(object):
    def __init__(self, ref):
        self.ref = ref

    def __call__(self, model, row):
        return HasManyViaSet(
            model.db, *RelationBuilder(self.ref, model).via(row))


class VirtualWrap(object):
    def __init__(self, model, virtual):
        self.model = model
        self.virtual = virtual

    def __call__(self, row, *args, **kwargs):
        if self.virtual.inject_model:
            row = row[self.model.tablename]
        return self.virtual.f(self.model, row, *args, **kwargs)


class ScopeWrap(object):
    def __init__(self, set, model, scope):
        self.set = set
        self.model = model
        self.scope = scope

    def __call__(self, *args, **kwargs):
        return self.set.where(
            self.scope(self.model, *args, **kwargs), model=self.model)


class Callback(object):
    _inst_count_ = 0

    def __init__(self, f, t):
        self.t = []
        if isinstance(f, Callback):
            self.t += f.t
            f = f.f
        self.f = f
        self.t.append(t)
        self._inst_count_ = Callback._inst_count_
        Callback._inst_count_ += 1

    def __call__(self):
        return None


class JoinedIDReference(_IDReference):
    @classmethod
    def _from_record(cls, record, table=None):
        rv = cls(record.id)
        rv._table = table
        rv._record = record
        return rv

    def as_dict(self, datetime_to_str=False, custom_types=None):
        return self._record.as_dict()


class JoinSet(Set):
    @classmethod
    def _from_set(cls, obj, table, joins):
        rv = cls(
            obj.db, obj.query, obj.query.ignore_common_filters)
        rv._stable_ = table
        rv._joins_ = joins
        return rv

    def select(self, *fields, **options):
        #: use iterselect for performance
        rows = super(Set, self).iterselect(*fields, **options)
        #: build new colnames
        colnames = []
        jcolnames = {}
        for colname in rows.colnames:
            tname, cname = colname.split('.')
            if tname == self._stable_:
                colnames.append(cname)
            else:
                if jcolnames.get(tname) is None:
                    jcolnames[tname] = []
                jcolnames[tname].append(cname)
        #: rebuild rowset using nested objects
        records = []
        _last_rid = None
        for record in rows:
            #: since we have multiple rows for the same id, we take them once
            if record[self._stable_].id != _last_rid:
                records.append(record[self._stable_])
                #: prepare nested rows
                for join in self._joins_:
                    if not join[2]:
                        records[-1][join[0]] = Rows(
                            self.db, [], jcolnames[join[1]], compact=False)
            _last_rid = record[self._stable_].id
            #: add joins in nested Rows objects
            for join in self._joins_:
                if join[2]:
                    records[-1][join[0]] = JoinedIDReference._from_record(
                        record[join[1]], self.db[join[1]])
                else:
                    records[-1][join[0]].records.append(record[join[1]])
        return JoinRows(
            self.db, records, colnames, compact=False, jtables=self._joins_)


class LeftJoinSet(Set):
    @classmethod
    def _from_set(cls, obj, jdata):
        rv = cls(
            obj.db, obj.query, obj.query.ignore_common_filters, obj._model_)
        rv._jdata_ = jdata
        return rv

    def select(self, *fields, **options):
        #: collect tablenames
        table = self._model_.tablename
        jtables = []
        for index, join in enumerate(options['left']):
            jdata = self._jdata_[index]
            jtables.append((jdata[0], join.first._tablename, jdata[1]))
        #: use iterselect for performance
        rows = super(Set, self).iterselect(*fields, **options)
        #: build new colnames
        colnames = []
        jcolnames = {}
        for colname in rows.colnames:
            tname, cname = colname.split('.')
            if tname == table:
                colnames.append(cname)
            else:
                if jcolnames.get(tname) is None:
                    jcolnames[tname] = []
                jcolnames[tname].append(cname)
        #: rebuild rowset using nested objects
        records = []
        _last_rid = None
        for record in rows:
            #: since we have multiple rows for the same id, we take them once
            if record[table].id != _last_rid:
                records.append(record[table])
                #: prepare nested rows
                for join in jtables:
                    if not join[2]:
                        records[-1][join[0]] = Rows(
                            self.db, [], jcolnames[join[1]], compact=False)
            _last_rid = record[table].id
            #: add joins in nested Rows objects
            for join in jtables:
                if record[join[1]].id is not None:
                    if join[2]:
                        records[-1][join[0]] = JoinedIDReference._from_record(
                            record[join[1]], self.db[join[1]])
                    else:
                        records[-1][join[0]].records.append(record[join[1]])
        return JoinRows(
            self.db, records, colnames, compact=False, jtables=jtables)


class JoinRows(Rows):
    def __init__(self, *args, **kwargs):
        self._joins_ = kwargs['jtables']
        del kwargs['jtables']
        super(JoinRows, self).__init__(*args, **kwargs)

    def as_list(self, compact=True, storage_to_dict=True,
                datetime_to_str=False, custom_types=None):
        (oc, self.compact) = (self.compact, compact)
        if storage_to_dict:
            items = []
            for row in self:
                item = row.as_dict(datetime_to_str, custom_types)
                for jdata in self._joins_:
                    if not jdata[2]:
                        item[jdata[0]] = row[jdata[0]].as_list()
                items.append(item)
        else:
            items = [item for item in self]
        self.compact = oc
        return items


class TimingHandler(ExecutionHandler):
    def _timings(self):
        THREAD_LOCAL._weppydal_timings_ = getattr(
            THREAD_LOCAL, '_weppydal_timings_', [])
        return THREAD_LOCAL._weppydal_timings_

    @cachedprop
    def timings(self):
        return self._timings()

    def before_execute(self, command):
        self.t = time.time()

    def after_execute(self, command):
        dt = time.time() - self.t
        self.timings.append((command, dt))


def make_tablename(classname):
    words = re.findall('[A-Z][^A-Z]*', classname)
    tablename = '_'.join(words)
    return tablename.lower() + "s"
