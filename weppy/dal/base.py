# -*- coding: utf-8 -*-
"""
    weppy.dal.base
    --------------

    Provides base pyDAL implementation for weppy.

    :copyright: (c) 2014-2016 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

import os
from pydal import DAL as _pyDAL, Field as _Field
from pydal._globals import THREAD_LOCAL
from pydal.objects import Table as _Table, Set as _Set, Rows as _Rows, \
    Expression, Row
from .._compat import copyreg, iterkeys
from ..datastructures import sdict
from ..handlers import Handler
from ..security import uuid as _uuid
from ..serializers import _custom_json, xml
from ..utils import cachedprop
from ..validators import ValidateFromDict


class DALHandler(Handler):
    def __init__(self, db):
        self.db = db

    def on_start(self):
        self.db._adapter.reconnect()

    def on_success(self):
        self.db.commit()

    def on_failure(self):
        self.db.rollback()

    def on_end(self):
        self.db._adapter.close()


class Table(_Table):
    def _create_references(self):
        self._referenced_by = []
        self._referenced_by_list = []
        self._references = []


class Set(_Set):
    def __init__(self, db, query, ignore_common_filters=None, model=None):
        super(Set, self).__init__(db, query, ignore_common_filters)
        self._model_ = model
        self._scopes_ = {}
        self._load_scopes_()

    def _load_scopes_(self):
        if self._model_ is None:
            tables = self.db._adapter.tables(self.query)
            if len(tables) == 1:
                self._model_ = self.db[tables[0]]._model_
        if self._model_:
            self._scopes_ = self._model_._scopes_

    def where(self, query, ignore_common_filters=False, model=None):
        if query is None:
            return self
        elif isinstance(query, Table):
            query = self.db._adapter.id_query(query)
        elif isinstance(query, str):
            query = Expression(self.db, query)
        elif isinstance(query, Field):
            query = query != None
        q = self.query & query if self.query else query
        return Set(
            self.db, q, ignore_common_filters=ignore_common_filters,
            model=model)

    def select(self, *fields, **options):
        pagination = options.get('paginate')
        if pagination:
            if isinstance(pagination, tuple):
                offset = pagination[0]
                limit = pagination[1]
            else:
                offset = pagination
                limit = 10
            options['limitby'] = ((offset - 1) * limit, offset * limit)
            del options['paginate']
        including = options.get('including')
        if including and self._model_ is not None:
            from .helpers import LeftJoinSet
            options['left'], jdata = self._parse_left_rjoins(including)
            del options['including']
            #: add fields to select
            fields = list(fields)
            if not fields:
                fields = [self._model_.table.ALL]
            for join in options['left']:
                fields.append(join.first.ALL)
            return LeftJoinSet._from_set(
                self, jdata).select(*fields, **options)
        return super(Set, self).select(*fields, **options)

    def join(self, *args):
        rv = self
        if self._model_ is not None:
            joins = []
            jtables = []
            for arg in args:
                join_data = self._parse_rjoin(arg)
                joins.append(join_data[0])
                jtables.append((arg, join_data[1]._tablename, join_data[2]))
            if joins:
                from .helpers import JoinSet
                q = joins[0]
                for join in joins[1:]:
                    q = q & join
                rv = rv.where(q)
                return JoinSet._from_set(rv, self._model_.tablename, jtables)
        return rv

    def _parse_rjoin(self, arg):
        from .helpers import RelationBuilder
        #: match has_many
        rel = self._model_._hasmany_ref_.get(arg)
        if rel:
            if isinstance(rel, dict) and rel.get('via'):
                r = RelationBuilder(rel, self._model_).via()
                return r[0], r[1]._table, False
            else:
                r = RelationBuilder(rel, self._model_)
                return r.many(), rel.table, False
        #: match belongs_to and refers_to
        rel = self._model_._belongs_ref_.get(arg)
        if rel:
            r = RelationBuilder((rel, arg), self._model_).belongs_query()
            return r, self._model_.db[rel], True
        #: match has_one
        rel = self._model_._hasone_ref_.get(arg)
        if rel:
            r = RelationBuilder(rel, self._model_)
            return r.many(), rel.table, False
        raise RuntimeError(
            'Unable to find %s relation of %s model' %
            (arg, self._model_.__name__))

    def _parse_left_rjoins(self, args):
        if not isinstance(args, (list, tuple)):
            args = [args]
        joins = []
        jdata = []
        for arg in args:
            join = self._parse_rjoin(arg)
            joins.append(join[1].on(join[0]))
            jdata.append((arg, join[2]))
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
            from .helpers import ScopeWrap
            return ScopeWrap(self, self._model_, scope.f)
        raise AttributeError(name)


class Rows(_Rows):
    def __init__(self, db=None, records=[], colnames=[], compact=True,
                 rawrows=None):
        self.db = db
        self.records = records
        self.colnames = colnames
        self._rowkeys_ = list(self.records[0].keys()) if self.records else []
        self._getrow = self._getrow_compact_ if self.compact else self._getrow_

    @cachedprop
    def compact(self):
        if not self.records:
            return True
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


class DAL(_pyDAL):
    serializers = {'json': _custom_json, 'xml': xml}
    logger = None
    uuid = lambda x: _uuid()

    record_operators = {}
    execution_handlers = []

    Rows = Rows

    @staticmethod
    def uri_from_config(config=None):
        if config is None or config.adapter is None:
            config = sdict(adapter="sqlite", host="dummy.db")
        if config.adapter == "<zombie>":
            return config.adapter
        if config.adapter == "sqlite" and config.host == "memory":
            return config.adapter + ":" + config.host
        uri = config.adapter + "://"
        if config.user:
            uri = uri + config.user + ":" + config.password + "@"
        uri = uri + config.host
        if config.database:
            uri += "/" + config.database
        return uri

    def __new__(cls, app, *args, **kwargs):
        config = kwargs.get('config', sdict()) or app.config.db
        uri = config.uri or DAL.uri_from_config(config)
        return super(DAL, cls).__new__(cls, uri, *args, **kwargs)

    def __init__(self, app, config=sdict(), pool_size=None, folder=None,
                 **kwargs):
        self.logger = app.log
        config = config or app.config.db
        if not config.uri:
            config.uri = self.uri_from_config(config)
        self.config = config
        #: load config data
        kwargs['check_reserved'] = self.config.check_reserved or \
            kwargs.get('check_reserved', None)
        kwargs['migrate'] = self.config.auto_migrate or \
            kwargs.get('auto_migrate', True)
        kwargs['driver_args'] = self.config.driver_args or \
            kwargs.get('driver_args', None)
        kwargs['adapter_args'] = self.config.adapter_args or \
            kwargs.get('adapter_args', None)
        if kwargs.get('auto_migrate') is not None:
            del kwargs['auto_migrate']
        #: set directory
        folder = folder or 'databases'
        folder = os.path.join(app.root_path, folder)
        if not os.path.exists(folder):
            os.mkdir(folder)
        #: set pool_size
        pool_size = self.config.pool_size or pool_size or 0
        #: add timings storage if requested
        if config.store_execution_timings:
            from .helpers import TimingHandler
            self.execution_handlers.append(TimingHandler)
        #: finally setup pyDAL instance
        super(DAL, self).__init__(self.config.uri, pool_size, folder, **kwargs)
        self._adapter._add_operators_to_parsed_row = \
            lambda *args, **kwargs: None
        self._adapter._add_reference_sets_to_parsed_row = \
            lambda *args, **kwargs: None

    @property
    def handler(self):
        return DALHandler(self)

    @property
    def execution_timings(self):
        return getattr(THREAD_LOCAL, '_weppydal_timings_', [])

    def define_models(self, *models):
        if len(models) == 1 and isinstance(models[0], (list, tuple)):
            models = models[0]
        for model in models:
            if not hasattr(self, model.__name__):
                # store db instance inside model
                model.db = self
                # init model
                obj = model()
                obj._define_props_()
                obj._define_relations_()
                obj._define_virtuals_()
                # define table and store in model
                #model.fields = obj.fields
                args = dict(
                    migrate=obj.migrate,
                    format=obj.format,
                    table_class=Table
                )
                model.table = self.define_table(
                    obj.tablename, *obj.fields, **args
                )
                model.table._model_ = obj
                model.id = model.table.id
                # load user's definitions
                obj._define_()
                # set reference in db for model name
                self.__setattr__(model.__name__, obj.table)

    def where(self, query=None, ignore_common_filters=None, model=None):
        q = None
        if isinstance(query, Table):
            q = self._adapter.id_query(query)
        elif isinstance(query, Field):
            q = (query != None)
        elif isinstance(query, dict):
            icf = query.get("ignore_common_filters")
            if icf:
                ignore_common_filters = icf
        if q is None and query is not None:
            if hasattr(query, '_belongs_ref_'):
                q = self._adapter.id_query(query.table)
            else:
                q = query
        return Set(
            self, q, ignore_common_filters=ignore_common_filters, model=model)


def _DAL_unpickler(db_uid):
    fake_app_obj = sdict(config=sdict(db=sdict()))
    fake_app_obj.config.db.adapter = '<zombie>'
    return DAL(fake_app_obj, db_uid=db_uid)


def _DAL_pickler(db):
    return _DAL_unpickler, (db._db_uid,)

copyreg.pickle(DAL, _DAL_pickler, _DAL_unpickler)


class Field(_Field):
    _weppy_types = {
        'integer': 'int', 'double': 'float', 'bigint': 'int',
        'boolean': 'bool', 'list:integer': 'list:int'
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
        if self._type == 'bool':
            rv['in'] = (False, True)
        if self._type in ['string', 'text', 'password']:
            rv['len'] = {'lte': self.length}
        if self._type == 'password':
            rv['len']['gte'] = 6
            rv['crypt'] = True
        if self._type == 'list:int':
            rv['is'] = {'list:int'}
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
