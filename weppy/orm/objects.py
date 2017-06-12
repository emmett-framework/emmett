# -*- coding: utf-8 -*-
"""
    weppy.orm.objects
    -----------------

    Provides pyDAL objects implementation for weppy.

    :copyright: (c) 2014-2017 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

import copy
import datetime
import decimal
import types
from collections import OrderedDict, defaultdict
from pydal.objects import (
    Table as _Table, Field as _Field, Set as _Set,
    Row as _Row, Rows as _Rows, IterRows as _IterRows, Query, Expression)
from .._compat import (
    string_types, integer_types, implements_iterator, implements_to_string,
    iterkeys, iteritems, to_unicode)
from ..datastructures import sdict
from ..globals import current
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
    _weppy_types = {
        'integer': 'int', 'double': 'float', 'boolean': 'bool',
        'list:integer': 'list:int'
    }
    _pydal_types = {
        'int': 'integer', 'bool': 'boolean', 'list:int': 'list:integer'
    }
    _weppy_delete = {
        'cascade': 'CASCADE', 'nullify': 'SET NULL', 'nothing': 'NO ACTION'
    }
    _inst_count_ = 0
    _obj_created_ = False

    def __init__(self, type='string', *args, **kwargs):
        self.modelname = None
        self._auto_validation = True
        #: convert type
        self._type = self._weppy_types.get(type, type)
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
            if _ondelete not in list(self._weppy_delete):
                raise SyntaxError(
                    'Field ondelete should be set on %s, %s or %s' %
                    list(self._weppy_delete)
                )
            kwargs['ondelete'] = self._weppy_delete[_ondelete]
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
            'int', 'float', 'decimal', 'date', 'time', 'datetime', 'json'
        ]
        if self._type in auto_types:
            rv['is'] = self._type
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
        if self.notnull or self._type.startswith('reference') or \
                self._type.startswith('list:reference'):
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
    #  it will make weppy's Field class compatible with the pyDAL's one
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

    def where(self, query, ignore_common_filters=False, model=None):
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
        return Set(
            self.db, q, ignore_common_filters=ignore_common_filters,
            model=model)

    def select(self, *fields, **options):
        pagination, including = options.get('paginate'), None
        if pagination:
            if isinstance(pagination, tuple):
                offset = pagination[0]
                limit = pagination[1]
            else:
                offset = pagination
                limit = 10
            options['limitby'] = ((offset - 1) * limit, offset * limit)
            del options['paginate']
        if 'including' in options:
            including = options['including']
            del options['including']
        if including and self._model_ is not None:
            options['left'], jdata = self._parse_left_rjoins(including)
            #: add fields to select
            fields = list(fields)
            if not fields:
                fields = [self._model_.table.ALL]
            for join in options['left']:
                fields.append(join.first.ALL)
            return LeftJoinSet._from_set(
                self, jdata).select(*fields, **options)
        return super(Set, self).select(*fields, **options)

    def validate_and_update(self, **update_fields):
        table = self.db._adapter.get_table(self.query)
        current._dbvalidation_record_id_ = None
        if table._unique_fields_validation_ and self.count() == 1:
            if any(
                table._unique_fields_validation_.get(fieldname)
                for fieldname in iterkeys(update_fields)
            ):
                current._dbvalidation_record_id_ = \
                    self.select(table.id).first().id
        response = Row()
        response.errors = Row()
        new_fields = copy.copy(update_fields)
        for key, value in iteritems(update_fields):
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
            jtables = []
            for arg in args:
                condition, table, rel_type = self._parse_rjoin(arg)
                joins.append(condition)
                jtables.append((arg, table._tablename, rel_type))
            if joins:
                q = joins[0]
                for join in joins[1:]:
                    q = q & join
                rv = rv.where(q)
                return JoinSet._from_set(rv, self._model_.tablename, jtables)
        return rv

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
            jdata.append((arg, rel_type))
        return joins, jdata

    def _jcolnames_from_rowstmps(self, tmps):
        colnames = []
        all_colnames = {}
        jcolnames = {}
        for colname in tmps:
            all_colnames[colname[0]] = colname[0]
            jcolnames[colname[0]] = jcolnames.get(colname[0], [])
            jcolnames[colname[0]].append(colname[1])
        for colname in iterkeys(all_colnames):
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
        rv = False
        if 'reload' in kwargs:
            rv = kwargs['reload']
            del kwargs['reload']
        return rv

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
        return self.select().first()

    def __call__(self, *args, **kwargs):
        refresh = self._filter_reload(kwargs)
        if not args and not kwargs:
            return self._last_resultset(refresh)
        return self.select(*args, **kwargs).first()


class HasManySet(RelationSet):
    def _cache_resultset(self):
        return self.select()

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


class JoinableSet(Set):
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

    def _build_records_from_joined(self, rowmap, inclusions, joins, colnames):
        for rid, many_data in iteritems(inclusions):
            for jname, included in iteritems(many_data):
                rowmap[rid][jname]._cached_resultset = Rows(
                    self.db, list(included.values()), [])
        return JoinRows(
            self.db, list(rowmap.values()), colnames, jtables=joins)


class JoinSet(JoinableSet):
    @classmethod
    def _from_set(cls, obj, table, joins):
        rv = cls(
            obj.db, obj.query, obj.query.ignore_common_filters)
        rv._stable_ = table
        rv._joins_ = joins
        return rv

    def select(self, *fields, **options):
        belongs_joins, one_joins, many_joins = self._split_joins(self._joins_)
        #: use iterselect for performance
        rows = self._iterselect_rows(*fields, **options)
        #: rebuild rowset using nested objects
        rowmap = OrderedDict()
        inclusions = defaultdict(
            lambda: {jname: OrderedDict() for jname, jtable in many_joins})
        for row in rows:
            rid = row[self._stable_].id
            rowmap[rid] = rowmap.get(rid, row[self._stable_])
            for jname, jtable in belongs_joins:
                rowmap[rid][jname] = JoinedIDReference._from_record(
                    row[jtable], self.db[jtable])
            for jname, jtable in one_joins:
                rowmap[rid][jname]._cached_resultset = row[jtable]
            for jname, jtable in many_joins:
                inclusions[rid][jname][row[jtable].id] = \
                    inclusions[rid][jname].get(
                        row[jtable].id, row[jtable])
        return self._build_records_from_joined(
            rowmap, inclusions, self._joins_, rows.colnames)


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
        jtypes = {'belongs': [], 'one': [], 'many': []}
        jtables = []
        for index, join in enumerate(options['left']):
            jname, rel_type = self._jdata_[index]
            tname = join.first._tablename
            jtables.append((jname, tname, rel_type))
            jtypes[rel_type].append((jname, tname))
        #: use iterselect for performance
        rows = self._iterselect_rows(*fields, **options)
        #: rebuild rowset using nested objects
        rowmap = OrderedDict()
        inclusions = defaultdict(
            lambda: {jname: OrderedDict() for jname, jtable in jtypes['many']})
        for row in rows:
            rid = row[self._stable_].id
            rowmap[rid] = rowmap.get(rid, row[self._stable_])
            for jname, jtable in jtypes['belongs']:
                if row[jtable].id:
                    rowmap[rid][jname] = JoinedIDReference._from_record(
                        row[jtable], self.db[jtable])
            for jname, jtable in jtypes['one']:
                if row[jtable].id:
                    rowmap[rid][jname]._cached_resultset = row[jtable]
            for jname, jtable in jtypes['many']:
                if row[jtable].id:
                    inclusions[rid][jname][row[jtable].id] = \
                        inclusions[rid][jname].get(
                            row[jtable].id, row[jtable])
        return self._build_records_from_joined(
            rowmap, inclusions, jtables, rows.colnames)


@implements_to_string
class Row(_Row):
    _as_dict_types_ = tuple(
        [type(None)] + list(integer_types) + [float, bool, list, dict] +
        list(string_types) + [datetime.datetime, datetime.date, datetime.time])

    def as_dict(self, datetime_to_str=False, custom_types=None):
        rv = {}
        for key, val in self.iteritems():
            if isinstance(val, Row):
                val = val.as_dict()
            elif isinstance(val, _IDReference):
                val = integer_types[-1](val)
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
        return u'<Row %s>' % to_unicode(self.as_dict())

    def __repr__(self):
        return str(self)


@implements_to_string
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
        return to_unicode(self.records)


@implements_iterator
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


class JoinRows(Rows):
    def __init__(self, *args, **kwargs):
        self._joins_ = kwargs['jtables']
        del kwargs['jtables']
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
