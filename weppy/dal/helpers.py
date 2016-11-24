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
from collections import OrderedDict
from pydal._globals import THREAD_LOCAL
from pydal.objects import Query, IterRows as _IterRows
from pydal.helpers.classes import Reference as _IDReference, ExecutionHandler
from .._compat import implements_iterator, iteritems
from ..datastructures import sdict
from ..utils import cachedprop
from .base import Set, Field, Rows


class Reference(object):
    def __init__(self, *args, **params):
        self.reference = [arg for arg in args]
        self.params = params
        self.refobj[id(self)] = self

    def __call__(self, func):
        if self.__class__.__name__ not in ['has_one', 'has_many']:
            raise SyntaxError(
                '%s cannot be used as a decorator' % self.__class__.__name__)
        if not callable(func):
            raise SyntaxError('Argument must be callable')
        if self.reference:
            raise SyntaxError(
                "When using %s as decorator, you must use the 'field' option" %
                self.__class__.__name__)
        new_reference = {func.__name__: {'method': func}}
        field = self.params.get('field')
        if field:
            new_reference[func.__name__]['field'] = field
        self.reference = [new_reference]
        return self

    @property
    def refobj(self):
        return {}


class ReferenceData(sdict):
    def __init__(self, model_class, **kwargs):
        self.model_class = model_class
        super(ReferenceData, self).__init__(**kwargs)

    @cachedprop
    def dbset(self):
        if self.method:
            return self.method(self.model_class)
        return self.model_class.db

    @cachedprop
    def model_instance(self):
        if self.method:
            return self.dbset._model_
        return self.dbset[self.model]._model_

    @property
    def table(self):
        return self.model_instance.table

    @property
    def table_name(self):
        return self.model_instance.tablename

    @property
    def field_instance(self):
        return self.table[self.field]


class RelationBuilder(object):
    def __init__(self, ref, model):
        self.ref = ref
        self.model = model

    def _make_refid(self, row):
        return row.id if row is not None else self.model.id

    def _extra_scopes(self, ref, model_instance=None):
        model_instance = model_instance or ref.model_instance
        rv = []
        if ref.scope is not None:
            scope_m = model_instance._scopes_[ref.scope].f
            rv.append(lambda f=scope_m, m=model_instance: f(m))
        if ref.where is not None:
            rv.append(lambda f=ref.where, m=model_instance: f(m))
        return rv

    def _patch_query_with_scopes(self, ref, query):
        for scope in self._extra_scopes(ref):
            query = query & scope()
        return query

    def _patch_query_with_scopes_on(self, ref, query, model_name):
        model = self.model.db[model_name]._model_
        for scope in self._extra_scopes(ref, model):
            query = query & scope()
        return query

    def _get_belongs(self, modelname, value):
        return self.model.db[modelname]._model_._belongs_ref_.get(value)

    def belongs_query(self):
        return (self.model.table[self.ref[1]] == self.model.db[self.ref[0]].id)

    @staticmethod
    def many_query(ref, rid):
        return ref.model_instance.table[ref.field] == rid

    def _many(self, ref, rid):
        return ref.dbset.where(
            self._patch_query_with_scopes(ref, self.many_query(ref, rid))
        ).query

    def many(self, row=None):
        return self._many(self.ref, self._make_refid(row))

    def via(self, row=None):
        db = self.model.db
        rid = self._make_refid(row)
        sname = self.model.__class__.__name__
        stack = []
        midrel = self.model._hasmany_ref_[self.ref.via]
        stack.append(self.ref)
        while midrel.via is not None:
            stack.insert(0, midrel)
            midrel = self.model._hasmany_ref_[midrel.via]
        query = self._many(midrel, rid)
        step_model = midrel.table_name
        sel_field = db[step_model].ALL
        last_belongs = None
        last_via = None
        for via in stack:
            rname = via.field or via.name[:-1]
            belongs_model = self._get_belongs(step_model, rname)
            if belongs_model:
                #: join table way
                last_belongs = step_model
                last_via = via
                _query = (db[belongs_model].id == db[step_model][rname])
                sel_field = db[belongs_model].ALL
                step_model = belongs_model
            else:
                #: shortcut way
                last_belongs = None
                rname = via.field or via.name
                midrel = db[step_model]._model_._hasmany_ref_[rname]
                _query = self._many(midrel, db[step_model].id)
                step_model = midrel.table_name
                sel_field = db[step_model].ALL
            query = query & _query
        query = via.dbset.where(
            self._patch_query_with_scopes_on(via, query, step_model)).query
        return query, sel_field, sname, rid, last_belongs, last_via


class RelationSet(object):
    _relation_method_ = 'many'

    def __init__(self, db, relation_builder, row):
        self.db = db
        self._relation_ = relation_builder
        self._row_ = row

    def _get_query_(self):
        try:
            return getattr(self._relation_, self._relation_method_)(self._row_)
        except AttributeError as e:
            raise RuntimeError(e.message)
        except Exception:
            raise

    @property
    def _model_(self):
        return self._relation_.ref.model_instance

    @cachedprop
    def _field_(self):
        return self._relation_.ref.field_instance

    @cachedprop
    def _scopes_(self):
        if self._relation_.ref.method:
            return [lambda: self._relation_.ref.dbset.query]
        return self._relation_._extra_scopes(self._relation_.ref)

    @cachedprop
    def _set(self):
        return Set(self.db, self._get_query_(), model=self._model_)

    def __getattr__(self, name):
        return getattr(self._set, name)

    def __repr__(self):
        return repr(self._set)

    def __call__(self, query, ignore_common_filters=False):
        return self._set.where(query, ignore_common_filters)

    def select(self, *args, **kwargs):
        if 'reload' in kwargs:
            del kwargs['reload']
        return self._set.select(*args, **kwargs)

    def create(self, **kwargs):
        attributes = self._get_fields_from_scopes(
            self._scopes_, self._model_.tablename)
        attributes.update(**kwargs)
        attributes[self._field_.name] = self._row_.id
        return self._model_.create(
            **attributes
        )

    @staticmethod
    def _get_fields_from_scopes(scopes, table_name):
        rv = {}
        for scope in scopes:
            query = scope()
            components = [query.second, query.first]
            current_kv = []
            while components:
                component = components.pop()
                if isinstance(component, Query):
                    components.append(component.second)
                    components.append(component.first)
                else:
                    if isinstance(component, Field) and \
                       component._tablename == table_name:
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
        return HasOneSet(model.db, RelationBuilder(self.ref, model), row)


class HasManySet(RelationSet):
    @cachedprop
    def _last_resultset(self):
        return self.select()

    def __call__(self, *args, **kwargs):
        if not args and not kwargs:
            return self._last_resultset
        return self.select(*args, **kwargs)

    def add(self, obj):
        attributes = self._get_fields_from_scopes(
            self._scopes_, self._model_.tablename)
        attributes[self._field_.name] = self._row_.id
        return self.db(
            self.db[self._field_._tablename].id == obj.id
        ).validate_and_update(**attributes)

    def remove(self, obj):
        if self.db[self._field_._tablename][self._field_.name]._isrefers:
            return self.db(
                self._field_._table.id == obj.id).validate_and_update(
                **{self._field_.name: None}
            )
        return self.db(self._field_._table.id == obj.id).delete()


class HasManyWrap(object):
    def __init__(self, ref):
        self.ref = ref

    def __call__(self, model, row):
        return HasManySet(model.db, RelationBuilder(self.ref, model), row)


class HasManyViaSet(RelationSet):
    _relation_method_ = 'via'
    _via_error = "Can't %s elements in has_many relations without a join table"

    @cachedprop
    def _viadata(self):
        query, rfield, model_name, rid, via, viadata = \
            super(HasManyViaSet, self)._get_query_()
        return sdict(
            query=query, rfield=rfield, model_name=model_name, rid=rid,
            via=via, data=viadata
        )

    def _get_query_(self):
        return self._viadata.query

    @property
    def _model_(self):
        return self.db[self._viadata.model_name]._model_

    @cachedprop
    def _last_resultset(self):
        return self.select(self._viadata.rfield)

    def __call__(self, *args, **kwargs):
        if not args:
            if not kwargs:
                return self._last_resultset
            args = [self._viadata.rfield]
        return self.select(*args, **kwargs)

    def _get_relation_fields(self):
        viadata = self._viadata.data
        self_field = self._model_._hasmany_ref_[viadata.via].field
        rel_field = viadata.field or viadata.name[:-1]
        return self_field, rel_field

    def _fields_from_scopes(self):
        viadata = self._viadata.data
        rel = self._model_._hasmany_ref_[viadata.via]
        if rel.method:
            scopes = [lambda: rel.dbset.query]
        else:
            scopes = self._relation_._extra_scopes(rel)
        return self._get_fields_from_scopes(scopes, rel.table_name)

    def create(self, **kwargs):
        raise RuntimeError('Cannot create third objects for many relations')

    def add(self, obj, **kwargs):
        # works on join tables only!
        if self._viadata.via is None:
            raise RuntimeError(self._via_error % 'add')
        nrow = self._fields_from_scopes()
        nrow.update(**kwargs)
        #: get belongs references
        self_field, rel_field = self._get_relation_fields()
        nrow[self_field] = self._viadata.rid
        nrow[rel_field] = obj.id
        #: validate and insert
        return self.db[self._viadata.via]._model_.create(nrow)

    def remove(self, obj):
        # works on join tables only!
        if self._viadata.via is None:
            raise RuntimeError(self._via_error % 'remove')
        #: get belongs references
        self_field, rel_field = self._get_relation_fields()
        #: delete
        return self.db(
            (self.db[self._viadata.via][self_field] == self._viadata.rid) &
            (self.db[self._viadata.via][rel_field] == obj.id)).delete()


class HasManyViaWrap(object):
    def __init__(self, ref):
        self.ref = ref

    def __call__(self, model, row):
        return HasManyViaSet(model.db, RelationBuilder(self.ref, model), row)


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


class JoinableSet(Set):
    def _iterselect_rows(self, *fields, **attributes):
        tablenames = self.db._adapter.tables(
            self.query, attributes.get('join', None),
            attributes.get('left', None), attributes.get('orderby', None),
            attributes.get('groupby', None))
        fields = self.db._adapter.expand_all(fields, tablenames)
        colnames, sql = self.db._adapter._select_wcols(
            self.query, fields, **attributes)
        return JoinIterRows(self.db, sql, fields, colnames)

    def _split_joins(self, joins):
        one, many = [], []
        for jname, jtable, is_single_row in joins:
            if is_single_row:
                one.append((jname, jtable))
            else:
                many.append((jname, jtable))
        return one, many

    def _build_merged_row(self, row, many_joins):
        for jname, jtable in many_joins:
            row[jname] = OrderedDict()
        return row

    def _build_records_from_joined(self, joined, joins, many_joins, colnames):
        for rid, row in iteritems(joined):
            for jname, jtable in many_joins:
                row[jname] = Rows(self.db, list(row[jname].values()), [])
        return JoinRows(
            self.db, list(joined.values()), colnames, jtables=joins)


class JoinSet(JoinableSet):
    @classmethod
    def _from_set(cls, obj, table, joins):
        rv = cls(
            obj.db, obj.query, obj.query.ignore_common_filters)
        rv._stable_ = table
        rv._joins_ = joins
        return rv

    def select(self, *fields, **options):
        #: use iterselect for performance
        rows = self._iterselect_rows(*fields, **options)
        #: rebuild rowset using nested objects
        rowmap = OrderedDict()
        one_joins, many_joins = self._split_joins(self._joins_)
        for row in rows:
            rid = row[self._stable_].id
            rowmap[rid] = rowmap.get(
                rid, self._build_merged_row(row[self._stable_], many_joins)
            )
            for jname, jtable in one_joins:
                rowmap[rid][jname] = JoinedIDReference._from_record(
                    row[jtable], self.db[jtable])
            for jname, jtable in many_joins:
                rowmap[rid][jname][row[jtable].id] = rowmap[rid][jname].get(
                    row[jtable].id, row[jtable])
        return self._build_records_from_joined(
            rowmap, self._joins_, many_joins, rows.colnames)


class LeftJoinSet(JoinableSet):
    @classmethod
    def _from_set(cls, obj, jdata):
        rv = cls(
            obj.db, obj.query, obj.query.ignore_common_filters, obj._model_)
        rv._stable_ = rv._model_.tablename
        rv._jdata_ = jdata
        return rv

    def select(self, *fields, **options):
        #: collect tablenames
        jtables, one_joins, many_joins = [], [], []
        for index, join in enumerate(options['left']):
            jname, is_single_row = self._jdata_[index]
            tname = join.first._tablename
            jtables.append((jname, tname, is_single_row))
            if is_single_row:
                one_joins.append((jname, tname))
            else:
                many_joins.append((jname, tname))
        #: use iterselect for performance
        rows = self._iterselect_rows(*fields, **options)
        #: rebuild rowset using nested objects
        rowmap = OrderedDict()
        for row in rows:
            rid = row[self._stable_].id
            rowmap[rid] = rowmap.get(
                rid, self._build_merged_row(row[self._stable_], many_joins)
            )
            for jname, jtable in one_joins:
                if row[jtable].id:
                    rowmap[rid][jname] = JoinedIDReference._from_record(
                        row[jtable], self.db[jtable])
            for jname, jtable in many_joins:
                if row[jtable].id:
                    rowmap[rid][jname][row[jtable].id] = \
                        rowmap[rid][jname].get(row[jtable].id, row[jtable])
        return self._build_records_from_joined(
            rowmap, jtables, many_joins, rows.colnames)


@implements_iterator
class JoinIterRows(_IterRows):
    def __init__(self, db, sql, fields, colnames):
        self.db = db
        self.fields = fields
        self.colnames = colnames
        (self.fields_virtual, self.fields_lazy, self.tmps) = \
            self.db._adapter._parse_expand_colnames(colnames)
        self.cursor = self.db._adapter.cursor
        self.db._adapter.execute(sql)
        self.db._adapter.lock_cursor(self.cursor)
        self._head = None
        self.last_item = None
        self.last_item_id = None
        self.blob_decode = True
        self.cacheable = False
        self.sql = sql

    def __next__(self):
        db_row = self.cursor.fetchone()
        if db_row is None:
            raise StopIteration
        return self.db._adapter._parse(
            db_row, self.tmps, self.fields, self.colnames, self.blob_decode,
            self.cacheable, self.fields_virtual, self.fields_lazy)


class JoinRows(Rows):
    def __init__(self, *args, **kwargs):
        self._joins_ = kwargs['jtables']
        del kwargs['jtables']
        super(JoinRows, self).__init__(*args, **kwargs)

    def as_list(self, compact=True, storage_to_dict=True,
                datetime_to_str=False, custom_types=None):
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
