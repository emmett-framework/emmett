# -*- coding: utf-8 -*-
"""
    emmett.orm.objects
    ------------------

    Provides pyDAL objects implementation for Emmett.

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

import copy
import datetime
import decimal
import types

from collections import OrderedDict, defaultdict
from pydal.objects import (
    Table as _Table, Field as _Field, Set as _Set,
    Row as _Row, Rows as _Rows, IterRows as _IterRows, Query, Expression)

from ..ctx import current
from ..datastructures import sdict
from ..html import tag
from ..serializers import xml_encode
from ..utils import cachedprop
from ..validators import ValidateFromDict
from .helpers import (
    _IDReference, JoinedIDReference, RelationBuilder, wrap_scope_on_set)


class Table(_Table):
    def __init__(self, *args, **kwargs):
        super(Table, self).__init__(*args, **kwargs)
        self._unique_fields_validation_ = {}

    def _create_references(self):
        self._referenced_by = []
        self._referenced_by_list = []
        self._references = []


class Field(_Field):
    _internal_types = {
        'integer': 'int',
        'double': 'float',
        'boolean': 'bool',
        'list:integer': 'list:int'
    }
    _pydal_types = {
        'int': 'integer',
        'bool': 'boolean',
        'list:int': 'list:integer',
    }
    _internal_delete = {
        'cascade': 'CASCADE', 'nullify': 'SET NULL', 'nothing': 'NO ACTION'
    }
    _inst_count_ = 0
    _obj_created_ = False

    def __init__(self, type='string', *args, **kwargs):
        self.modelname = None
        self._auto_validation = True
        #: convert type
        self._type = self._internal_types.get(type, type)
        #: convert 'rw' -> 'readable', 'writeable'
        if 'rw' in kwargs:
            if isinstance(kwargs['rw'], (tuple, list)):
                read, write = kwargs['rw']
            else:
                read = write = kwargs['rw']
            kwargs['readable'] = read
            kwargs['writable'] = write
            del kwargs['rw']
        #: convert 'info' -> 'comment'
        _info = kwargs.get('info')
        if _info:
            kwargs['comment'] = _info
            del kwargs['info']
        #: convert ondelete parameter
        _ondelete = kwargs.get('ondelete')
        if _ondelete:
            if _ondelete not in list(self._internal_delete):
                raise SyntaxError(
                    'Field ondelete should be set on %s, %s or %s' %
                    list(self._internal_delete)
                )
            kwargs['ondelete'] = self._internal_delete[_ondelete]
        #: process 'refers_to' fields
        self._isrefers = kwargs.get('_isrefers')
        if self._isrefers:
            del kwargs['_isrefers']
        #: get auto validation preferences
        if 'auto_validation' in kwargs:
            self._auto_validation = kwargs['auto_validation']
            del kwargs['auto_validation']
        #: intercept validation (will be processed by `_make_field`)
        self._requires = {}
        self._custom_requires = []
        if 'validation' in kwargs:
            if isinstance(kwargs['validation'], dict):
                self._requires = kwargs['validation']
            else:
                self._custom_requires = kwargs['validation']
                if not isinstance(self._custom_requires, list):
                    self._custom_requires = [self._custom_requires]
            del kwargs['validation']
        self._validation = {}
        self._vparser = ValidateFromDict()
        #: store args and kwargs for `_make_field`
        self._args = args
        self._kwargs = kwargs
        #: increase creation counter (used to keep order of fields)
        self._inst_count_ = Field._inst_count_
        Field._inst_count_ += 1

    def _default_validation(self):
        rv = {}
        auto_types = [
            'int', 'float', 'date', 'time', 'datetime', 'json'
        ]
        if self._type in auto_types:
            rv['is'] = self._type
        elif self._type.startswith('decimal'):
            rv['is'] = 'decimal'
        if self._type == 'bigint':
            rv['is'] = 'int'
        if self._type == 'bool':
            rv['in'] = (False, True)
        if self._type in ['string', 'text', 'password']:
            rv['len'] = {'lte': self.length}
        if self._type == 'password':
            rv['len']['gte'] = 6
            rv['crypt'] = True
        if self._type == 'list:int':
            rv['is'] = 'list:int'
        if (
            self.notnull or self._type.startswith('reference') or
            self._type.startswith('list:reference')
        ):
            rv['presence'] = True
        if not self.notnull and self._isrefers is True:
            rv['allow'] = 'empty'
        if self.unique:
            rv['unique'] = True
        return rv

    def _parse_validation(self):
        for key in list(self._requires):
            self._validation[key] = self._requires[key]
        self.requires = self._vparser(self, self._validation) + \
            self._custom_requires

    #: `_make_field` will be called by `Model` class or `Form` class
    #  it will make intenral Field class compatible with the pyDAL's one
    def _make_field(self, name, model=None):
        if self._obj_created_:
            return self
        if model is not None:
            self.modelname = model.__class__.__name__
        #: convert field type to pyDAL ones if needed
        ftype = self._pydal_types.get(self._type, self._type)
        #: create pyDAL's Field instance
        super(Field, self).__init__(name, ftype, *self._args, **self._kwargs)
        #: add automatic validation (if requested)
        if self._auto_validation:
            auto = True
            if self.modelname:
                auto = model.auto_validation
            if auto:
                self._validation = self._default_validation()
        #: validators
        if not self.modelname:
            self._parse_validation()
        self._obj_created_ = True
        return self

    def __str__(self):
        if self._obj_created_:
            return super(Field, self).__str__()
        return object.__str__(self)

    def __repr__(self):
        if self.modelname and hasattr(self, 'name'):
            return "<%s.%s (%s) field>" % (self.modelname, self.name,
                                           self._type)
        return super(Field, self).__repr__()

    @classmethod
    def string(cls, *args, **kwargs):
        return cls('string', *args, **kwargs)

    @classmethod
    def int(cls, *args, **kwargs):
        return cls('int', *args, **kwargs)

    @classmethod
    def bigint(cls, *args, **kwargs):
        return cls('bigint', *args, **kwargs)

    @classmethod
    def float(cls, *args, **kwargs):
        return cls('float', *args, **kwargs)

    @classmethod
    def text(cls, *args, **kwargs):
        return cls('text', *args, **kwargs)

    @classmethod
    def bool(cls, *args, **kwargs):
        return cls('bool', *args, **kwargs)

    @classmethod
    def blob(cls, *args, **kwargs):
        return cls('blob', *args, **kwargs)

    @classmethod
    def date(cls, *args, **kwargs):
        return cls('date', *args, **kwargs)

    @classmethod
    def time(cls, *args, **kwargs):
        return cls('time', *args, **kwargs)

    @classmethod
    def datetime(cls, *args, **kwargs):
        return cls('datetime', *args, **kwargs)

    @classmethod
    def decimal(cls, precision, scale, *args, **kwargs):
        return cls('decimal({},{})'.format(precision, scale), *args, **kwargs)

    @classmethod
    def json(cls, *args, **kwargs):
        return cls('json', *args, **kwargs)

    @classmethod
    def password(cls, *args, **kwargs):
        return cls('password', *args, **kwargs)

    @classmethod
    def upload(cls, *args, **kwargs):
        return cls('upload', *args, **kwargs)

    @classmethod
    def int_list(cls, *args, **kwargs):
        return cls('list:int', *args, **kwargs)

    @classmethod
    def string_list(cls, *args, **kwargs):
        return cls('list:string', *args, **kwargs)

    def cast(self, value, **kwargs):
        return Expression(
            self.db, self._dialect.cast, self,
            self._dialect.types[value] % kwargs, value)


class Set(_Set):
    def __init__(self, db, query, ignore_common_filters=None, model=None):
        super(Set, self).__init__(db, query, ignore_common_filters)
        self._model_ = model
        self._scopes_ = {}
        self._load_scopes_()

    def _load_scopes_(self):
        if self._model_ is None:
            tablemap = self.db._adapter.tables(self.query)
            if len(tablemap) == 1:
                self._model_ = tablemap.popitem()[1]._model_
        if self._model_:
            self._scopes_ = self._model_._instance_()._scopes_

    def _clone(self, ignore_common_filters=None, model=None, **changes):
        return self.__class__(
            self.db, changes.get('query', self.query),
            ignore_common_filters=ignore_common_filters,
            model=model or self._model_
        )

    def where(self, query, ignore_common_filters=None, model=None):
        if query is None:
            return self
        elif isinstance(query, Table):
            query = self.db._adapter.id_query(query)
        elif isinstance(query, str):
            query = Expression(self.db, query)
        elif isinstance(query, Field):
            query = query != None
        elif isinstance(query, types.LambdaType):
            model = model or self._model_
            if not model:
                raise ValueError(
                    "Too many models involved in the Set to use a lambda")
            query = query(model)
        q = self.query & query if self.query else query
        return self._clone(ignore_common_filters, model, query=q)

    def _parse_paginate(self, pagination):
        if isinstance(pagination, tuple):
            offset = pagination[0]
            limit = pagination[1]
        else:
            offset = pagination
            limit = 10
        return ((offset - 1) * limit, offset * limit)

    def _join_set_builder(self, obj, jdata, auto_select_tables):
        return JoinedSet._from_set(
            obj, jdata=jdata, auto_select_tables=auto_select_tables)

    def _left_join_set_builder(self, jdata):
        return JoinedSet._from_set(
            self, ljdata=jdata, auto_select_tables=[self._model_.table])

    def _run_select_(self, *fields, **options):
        return super(Set, self).select(*fields, **options)

    def _get_table_from_query(self):
        if self._model_:
            return self._model_.table
        return self.db._adapter.get_table(self.query)

    def select(self, *fields, **options):
        obj = self
        pagination, including = (
            options.pop('paginate', None), options.pop('including', None))
        if pagination:
            options['limitby'] = self._parse_paginate(pagination)
        if including and self._model_ is not None:
            options['left'], jdata = self._parse_left_rjoins(including)
            obj = self._left_join_set_builder(jdata)
        return obj._run_select_(*fields, **options)

    def update(self, **update_fields):
        table = self._get_table_from_query()
        row = table._fields_and_values_for_update(update_fields)
        if not row._values:
            raise ValueError("No fields to update")
        if any(f(self, row) for f in table._before_update):
            return 0
        ret = self.db._adapter.update(table, self.query, row.op_values())
        ret and [f(self, row) for f in table._after_update]
        return ret

    def validate_and_update(self, **update_fields):
        table = self._get_table_from_query()
        current._dbvalidation_record_id_ = None
        if table._unique_fields_validation_ and self.count() == 1:
            if any(
                table._unique_fields_validation_.get(fieldname)
                for fieldname in update_fields.keys()
            ):
                current._dbvalidation_record_id_ = \
                    self.select(table.id).first().id
        response = Row()
        response.errors = Row()
        new_fields = copy.copy(update_fields)
        for key, value in update_fields.items():
            value, error = table[key].validate(value)
            if error:
                response.errors[key] = '%s' % error
            else:
                new_fields[key] = value
        del current._dbvalidation_record_id_
        if response.errors:
            response.updated = None
        else:
            row = table._fields_and_values_for_update(new_fields)
            if not row._values:
                raise ValueError("No fields to update")
            if any(f(self, row) for f in table._before_update):
                ret = 0
            else:
                ret = self.db._adapter.update(
                    table, self.query, row.op_values())
                ret and [f(self, row) for f in table._after_update]
            response.updated = ret
        return response

    def join(self, *args):
        rv = self
        if self._model_ is not None:
            joins = []
            jdata = []
            auto_select_tables = [self._model_.table]
            for arg in args:
                condition, table, rel_type = self._parse_rjoin(arg)
                joins.append(condition)
                jdata.append((arg, table._tablename, rel_type))
                auto_select_tables.append(table)
            if joins:
                q = joins[0]
                for join in joins[1:]:
                    q = q & join
                rv = rv.where(q, model=self._model_)
                return self._join_set_builder(rv, jdata, auto_select_tables)
        return rv

    def switch(self, model):
        self._model_ = model
        return self

    def _parse_rjoin(self, arg):
        #: match has_many
        rel = self._model_._hasmany_ref_.get(arg)
        if rel:
            if isinstance(rel, dict) and rel.get('via'):
                r = RelationBuilder(rel, self._model_._instance_()).via()
                return r[0], r[1]._table, 'many'
            else:
                r = RelationBuilder(rel, self._model_._instance_())
                return r.many(), rel.table, 'many'
        #: match belongs_to and refers_to
        rel = self._model_._belongs_ref_.get(arg)
        if rel:
            r = RelationBuilder(
                (rel, arg), self._model_._instance_()
            ).belongs_query()
            return r, self._model_.db[rel], 'belongs'
        #: match has_one
        rel = self._model_._hasone_ref_.get(arg)
        if rel:
            r = RelationBuilder(rel, self._model_._instance_())
            return r.many(), rel.table, 'one'
        raise RuntimeError(
            'Unable to find %s relation of %s model' %
            (arg, self._model_.__name__))

    def _parse_left_rjoins(self, args):
        if not isinstance(args, (list, tuple)):
            args = [args]
        joins = []
        jdata = []
        for arg in args:
            condition, table, rel_type = self._parse_rjoin(arg)
            joins.append(table.on(condition))
            jdata.append((arg, table._tablename, rel_type))
        return joins, jdata

    def _jcolnames_from_rowstmps(self, tmps):
        colnames = []
        all_colnames = {}
        jcolnames = {}
        for colname in tmps:
            all_colnames[colname[0]] = colname[0]
            jcolnames[colname[0]] = jcolnames.get(colname[0], [])
            jcolnames[colname[0]].append(colname[1])
        for colname in all_colnames.keys():
            if colname == self._stable_:
                colnames.append(colname)
                del jcolnames[colname]
        return colnames, jcolnames

    def __getattr__(self, name):
        scope = self._scopes_.get(name)
        if scope:
            return wrap_scope_on_set(self, self._model_._instance_(), scope.f)
        raise AttributeError(name)


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
        return Set(self.db, self._get_query_(), model=self._model_.__class__)

    def __getattr__(self, name):
        return getattr(self._set, name)

    def __repr__(self):
        return repr(self._set)

    def __call__(self, query, ignore_common_filters=False):
        return self._set.where(query, ignore_common_filters)

    def _last_resultset(self, refresh=False):
        if refresh or not hasattr(self, '_cached_resultset'):
            self._cached_resultset = self._cache_resultset()
        return self._cached_resultset

    def _filter_reload(self, kwargs):
        return kwargs.pop('reload', False)

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
    def _cache_resultset(self):
        return self.select(self._model_.table.ALL, limitby=(0, 1)).first()

    def __call__(self, *args, **kwargs):
        refresh = self._filter_reload(kwargs)
        if not args and not kwargs:
            return self._last_resultset(refresh)
        kwargs['limitby'] = (0, 1)
        return self.select(*args, **kwargs).first()


class HasManySet(RelationSet):
    def _cache_resultset(self):
        return self.select(self._model_.table.ALL)

    def __call__(self, *args, **kwargs):
        refresh = self._filter_reload(kwargs)
        if not args and not kwargs:
            return self._last_resultset(refresh)
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

    def _cache_resultset(self):
        return self.select(self._viadata.rfield)

    def __call__(self, *args, **kwargs):
        refresh = self._filter_reload(kwargs)
        if not args:
            if not kwargs:
                return self._last_resultset(refresh)
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


class JoinedSet(Set):
    @classmethod
    def _from_set(cls, obj, jdata=[], ljdata=[], auto_select_tables=[]):
        rv = cls(
            obj.db, obj.query, obj.query.ignore_common_filters, obj._model_)
        rv._stable_ = obj._model_.tablename
        rv._jdata_ = list(jdata)
        rv._ljdata_ = list(ljdata)
        rv._auto_select_tables_ = list(auto_select_tables)
        return rv

    def _clone(self, ignore_common_filters=None, model=None, **changes):
        rv = super(JoinedSet, self)._clone(
            ignore_common_filters, model, **changes)
        rv._stable_ = self._stable_
        rv._jdata_ = self._jdata_
        rv._ljdata_ = self._ljdata_
        rv._auto_select_tables_ = self._auto_select_tables_
        return rv

    def _join_set_builder(self, obj, jdata, auto_select_tables):
        return JoinedSet._from_set(
            obj, jdata=self._jdata_ + jdata, ljdata=self._ljdata_,
            auto_select_tables=self._auto_select_tables_ + auto_select_tables)

    def _left_join_set_builder(self, jdata):
        return JoinedSet._from_set(
            self, jdata=self._jdata_, ljdata=self._ljdata_ + jdata,
            auto_select_tables=self._auto_select_tables_)

    def _iterselect_rows(self, *fields, **attributes):
        tablemap = self.db._adapter.tables(
            self.query, attributes.get('join', None),
            attributes.get('left', None), attributes.get('orderby', None),
            attributes.get('groupby', None))
        fields = self.db._adapter.expand_all(fields, tablemap)
        colnames, sql = self.db._adapter._select_wcols(
            self.query, fields, **attributes)
        return JoinIterRows(self.db, sql, fields, colnames)

    def _split_joins(self, joins):
        rv = {'belongs': [], 'one': [], 'many': []}
        for jname, jtable, rel_type in joins:
            rv[rel_type].append((jname, jtable))
        return rv['belongs'], rv['one'], rv['many']

    def _build_records_from_joined(self, rowmap, inclusions, colnames):
        for rid, many_data in inclusions.items():
            for jname, included in many_data.items():
                rowmap[rid][jname]._cached_resultset = Rows(
                    self.db, list(included.values()), [])
        return JoinRows(
            self.db, list(rowmap.values()), colnames,
            _jdata=self._jdata_ + self._ljdata_)

    def _run_select_(self, *fields, **options):
        #: build parsers
        belongs_j, one_j, many_j = self._split_joins(self._jdata_)
        belongs_l, one_l, many_l = self._split_joins(self._ljdata_)
        parsers = (
            self._build_jparsers(belongs_j, one_j, many_j) +
            self._build_lparsers(belongs_l, one_l, many_l)
        )
        #: auto add selection field for left joins
        if self._ljdata_:
            fields = list(fields)
            if not fields:
                fields = [v.ALL for v in self._auto_select_tables_]
            for join in options['left']:
                fields.append(join.first.ALL)
        #: use iterselect for performance
        rows = self._iterselect_rows(*fields, **options)
        #: rebuild rowset using nested objects
        rowmap = OrderedDict()
        inclusions = defaultdict(
            lambda: {
                jname: OrderedDict() for jname, jtable in (many_j + many_l)})
        for row in rows:
            rid = row[self._stable_].id
            rowmap[rid] = rowmap.get(rid, row[self._stable_])
            for parser in parsers:
                parser(rowmap, inclusions, row, rid)
        return self._build_records_from_joined(
            rowmap, inclusions, rows.colnames)

    def _build_jparsers(self, belongs, one, many):
        rv = []
        for jname, jtable in belongs:
            rv.append(self._jbelong_parser(jname, jtable, self.db))
        for jname, jtable in one:
            rv.append(self._jone_parser(jname, jtable))
        for jname, jtable in many:
            rv.append(self._jmany_parser(jname, jtable))
        return rv

    def _build_lparsers(self, belongs, one, many):
        rv = []
        for jname, jtable in belongs:
            rv.append(self._lbelong_parser(jname, jtable, self.db))
        for jname, jtable in one:
            rv.append(self._lone_parser(jname, jtable))
        for jname, jtable in many:
            rv.append(self._lmany_parser(jname, jtable))
        return rv

    @staticmethod
    def _jbelong_parser(fieldname, tablename, db):
        def parser(rowmap, inclusions, row, rid):
            rowmap[rid][fieldname] = JoinedIDReference._from_record(
                row[tablename], db[tablename])
        return parser

    @staticmethod
    def _jone_parser(fieldname, tablename):
        def parser(rowmap, inclusions, row, rid):
            rowmap[rid][fieldname]._cached_resultset = row[tablename]
        return parser

    @staticmethod
    def _jmany_parser(fieldname, tablename):
        def parser(rowmap, inclusions, row, rid):
            inclusions[rid][fieldname][row[tablename].id] = \
                inclusions[rid][fieldname].get(
                    row[tablename].id, row[tablename])
        return parser

    @staticmethod
    def _lbelong_parser(fieldname, tablename, db):
        def parser(rowmap, inclusions, row, rid):
            if not row[tablename].id:
                return
            rowmap[rid][fieldname] = JoinedIDReference._from_record(
                row[tablename], db[tablename])
        return parser

    @staticmethod
    def _lone_parser(fieldname, tablename):
        def parser(rowmap, inclusions, row, rid):
            if not row[tablename].id:
                return
            rowmap[rid][fieldname]._cached_resultset = row[tablename]
        return parser

    @staticmethod
    def _lmany_parser(fieldname, tablename):
        def parser(rowmap, inclusions, row, rid):
            if not row[tablename].id:
                return
            inclusions[rid][fieldname][row[tablename].id] = \
                inclusions[rid][fieldname].get(
                    row[tablename].id, row[tablename])
        return parser


class Row(_Row):
    _as_dict_types_ = tuple(
        [type(None)] + [int, float, bool, list, dict, str] +
        [datetime.datetime, datetime.date, datetime.time])

    def as_dict(self, datetime_to_str=False, custom_types=None):
        rv = {}
        for key, val in self.items():
            if isinstance(val, Row):
                val = val.as_dict()
            elif isinstance(val, _IDReference):
                val = int(val)
            elif isinstance(val, decimal.Decimal):
                val = float(val)
            elif not isinstance(val, self._as_dict_types_):
                continue
            rv[key] = val
        return rv

    def __getstate__(self):
        return self.as_dict()

    def __json__(self):
        return self.as_dict()

    def __xml__(self, key=None, quote=True):
        return xml_encode(self.as_dict(), key or 'row', quote)

    def __str__(self):
        return '<Row {}>'.format(self.as_dict())

    def __repr__(self):
        return str(self)

    def __getitem__(self, name):
        try:
            return super(Row, self).__getitem__(name)
        except KeyError:
            raise KeyError(name)

    def __getattr__(self, name):
        try:
            return self.__getitem__(name)
        except KeyError:
            raise AttributeError(name)


class Rows(_Rows):
    def __init__(
        self, db=None, records=[], colnames=[], compact=True, rawrows=None
    ):
        self.db = db
        self.records = records
        self.colnames = colnames
        self._rowkeys_ = list(self.records[0].keys()) if self.records else []
        self._getrow = self._getrow_compact_ if self.compact else self._getrow_

    @cachedprop
    def compact(self):
        if not self.records:
            return False
        return len(self._rowkeys_) == 1 and self._rowkeys_[0] != '_extra'

    @cachedprop
    def compact_tablename(self):
        if not self._rowkeys_:
            return None
        return self._rowkeys_[0]

    def _getrow_(self, i):
        return self.records[i]

    def _getrow_compact_(self, i):
        return self._getrow_(i)[self.compact_tablename]

    def __getitem__(self, i):
        if isinstance(i, slice):
            return self.__class__(self.db, self.records[i], self.colnames)
        return self._getrow(i)

    def column(self, column=None):
        colname = str(column) if column else self.colnames[0]
        return [r[colname] for r in self]

    def sorted(self, f, reverse=False):
        if self.compact:
            keyf = lambda r: f(r[self.compact_tablename])
        else:
            keyf = f
        return [r for r in sorted(self.records, key=keyf, reverse=reverse)]

    def sort(self, f, reverse=False):
        self.records = self.sorted(f, reverse)

    def append(self, obj):
        row = Row({self.compact_tablename: obj}) if self.compact else obj
        self.records.append(row)

    def insert(self, position, obj):
        row = Row({self.compact_tablename: obj}) if self.compact else obj
        self.records.insert(position, row)

    def render(self, *args, **kwargs):
        raise NotImplementedError

    def as_list(self, datetime_to_str=False, custom_types=None):
        return [item.as_dict(datetime_to_str, custom_types) for item in self]

    def as_dict(self, key='id', datetime_to_str=False, custom_types=None):
        if '.' in key:
            splitted_key = key.split('.')
            keyf = lambda row: row[splitted_key[0]][splitted_key[1]]
        else:
            keyf = lambda row: row[key]
        return {keyf(item): item for item in self.as_list()}

    def __json__(self):
        return [item.__json__() for item in self]

    def __xml__(self, key=None, quote=True):
        key = key or 'rows'
        return tag[key](*[item.__xml__(quote=quote) for item in self])

    def __str__(self):
        return str(self.records)


class JoinIterRows(_IterRows):
    def __init__(self, db, sql, fields, colnames):
        self.db = db
        self.fields = fields
        self.colnames = colnames
        self.fdata, self.tables = \
            self.db._adapter._parse_expand_colnames(fields)
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
            db_row, self.fdata, self.tables, self.fields, self.colnames,
            self.blob_decode)

    def __iter__(self):
        try:
            row = next(self)
            while row is not None:
                yield row
                row = next(self)
        except StopIteration:
            self.db._adapter.close_cursor(self.cursor)
        return


class JoinRows(Rows):
    def __init__(self, *args, **kwargs):
        self._joins_ = kwargs.pop('_jdata')
        super(JoinRows, self).__init__(*args, **kwargs)

    def as_list(
        self, compact=True, storage_to_dict=True, datetime_to_str=False,
        custom_types=None
    ):
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
