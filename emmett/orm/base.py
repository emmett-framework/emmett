# -*- coding: utf-8 -*-
"""
    emmett.orm.base
    ---------------

    Provides base pyDAL implementation for Emmett.

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

from __future__ import annotations

import copyreg
import os
import threading

from functools import wraps
from pydal import DAL as _pyDAL
from pydal._globals import THREAD_LOCAL

from ..datastructures import sdict
from ..extensions import Signals
from ..pipeline import Pipe
from ..security import uuid as _uuid
from ..serializers import _json_default, xml
from .adapters import patch_adapter
from .objects import Table, Field, Set, Row, Rows
from .helpers import ConnectionContext, TimingHandler
from .models import MetaModel, Model
from .transactions import _atomic, _transaction, _savepoint


class DatabasePipe(Pipe):
    def __init__(self, db):
        self.db = db

    async def open(self):
        await self.db.connection_open_loop()

    async def on_pipe_success(self):
        self.db.commit()

    async def on_pipe_failure(self):
        self.db.rollback()

    async def close(self):
        await self.db.connection_close_loop()


class Database(_pyDAL):
    serializers = {'json': _json_default, 'xml': xml}
    logger = None
    uuid = lambda x: _uuid()

    record_operators = {}
    execution_handlers = []

    Rows = Rows
    Row = Row

    _cls_global_lock_ = threading.RLock()

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
        uri = config.uri or Database.uri_from_config(config)
        return super(Database, cls).__new__(cls, uri, *args, **kwargs)

    def __init__(
        self,
        app,
        config=None,
        pool_size=None,
        keep_alive_timeout=3600,
        connect_timeout=60,
        folder=None,
        **kwargs
    ):
        app.send_signal(Signals.before_database)
        self.logger = app.log
        config = config or app.config.db
        if not config.uri:
            config.uri = self.uri_from_config(config)
        if not config.migrations_folder:
            config.migrations_folder = 'migrations'
        self.config = config
        self._auto_migrate = self.config.get(
            'auto_migrate', kwargs.pop('auto_migrate', False))
        self._auto_connect = self.config.get(
            'auto_connect', kwargs.pop('auto_connect', None))
        self._use_bigint_on_id_fields = self.config.get(
            'big_id_fields', kwargs.pop('big_id_fields', False))
        #: load config data
        kwargs['check_reserved'] = self.config.check_reserved or \
            kwargs.get('check_reserved', None)
        kwargs['migrate'] = self._auto_migrate
        kwargs['driver_args'] = self.config.driver_args or \
            kwargs.get('driver_args', None)
        kwargs['adapter_args'] = self.config.adapter_args or \
            kwargs.get('adapter_args', None)
        if self._auto_connect is not None:
            kwargs['do_connect'] = self._auto_connect
        else:
            kwargs['do_connect'] = os.environ.get('EMMETT_CLI_ENV') == 'true'
        if self._use_bigint_on_id_fields:
            kwargs['bigint_id'] = True
        #: set directory
        folder = folder or 'databases'
        folder = os.path.join(app.root_path, folder)
        if self._auto_migrate:
            with self._cls_global_lock_:
                if not os.path.exists(folder):
                    os.mkdir(folder)
        #: set pool_size
        pool_size = self.config.pool_size or pool_size or 5
        self._keep_alive_timeout = (
            keep_alive_timeout if self.config.keep_alive_timeout is None
            else self.config.keep_alive_timeout)
        self._connect_timeout = (
            connect_timeout if self.config.connect_timeout is None
            else self.config.connect_timeout)
        #: add timings storage if requested
        if config.store_execution_timings:
            self.execution_handlers.append(TimingHandler)
        #: finally setup pyDAL instance
        super(Database, self).__init__(
            self.config.uri, pool_size, folder, **kwargs)
        patch_adapter(self._adapter)
        Model._init_inheritable_dicts_()
        app.send_signal(Signals.after_database, database=self)

    @property
    def pipe(self):
        return DatabasePipe(self)

    @property
    def execution_timings(self):
        return getattr(THREAD_LOCAL, '_emtdal_timings_', [])

    def connection_open(self, with_transaction=True, reuse_if_open=True):
        return self._adapter.reconnect(
            with_transaction=with_transaction, reuse_if_open=reuse_if_open)

    def connection_close(self):
        self._adapter.close()

    def connection(
        self,
        with_transaction: bool = True,
        reuse_if_open: bool = True
    ) -> ConnectionContext:
        return ConnectionContext(
            self,
            with_transaction=with_transaction,
            reuse_if_open=reuse_if_open
        )

    def connection_open_loop(self, with_transaction=True, reuse_if_open=True):
        return self._adapter.reconnect_loop(
            with_transaction=with_transaction, reuse_if_open=reuse_if_open)

    def connection_close_loop(self):
        return self._adapter.close_loop()

    def define_models(self, *models):
        if len(models) == 1 and isinstance(models[0], (list, tuple)):
            models = models[0]
        if self._auto_migrate and not self._do_connect:
            self.connection_open()
        for model in models:
            if not hasattr(self, model.__name__):
                # store db instance inside model
                model.db = self
                # init model
                obj = model()
                obj._define_props_()
                obj._define_relations_()
                obj._define_virtuals_()
                obj._build_rowclass_()
                # define table and store in model
                args = dict(
                    migrate=obj.migrate,
                    format=obj.format,
                    table_class=Table
                )
                model.table = self.define_table(
                    obj.tablename, *obj.fields, **args
                )
                model.table._model_ = obj
                # load user's definitions
                obj._define_()
                # set reference in db for model name
                self.__setattr__(model.__name__, obj.table)
        if self._auto_migrate and not self._do_connect:
            self.connection_close()

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
            if isinstance(query, MetaModel):
                q = self._adapter.id_query(query.table)
            else:
                q = query
        return Set(
            self, q, ignore_common_filters=ignore_common_filters, model=model)

    def with_connection(self, f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            with self.connection():
                f(*args, **kwargs)
        return wrapped

    def atomic(self):
        return _atomic(self._adapter)

    def transaction(self):
        return _transaction(self._adapter)

    def savepoint(self):
        return _savepoint(self._adapter)

    def commit(self):
        txn = self._adapter.top_transaction()
        if txn:
            txn.commit()

    def rollback(self):
        txn = self._adapter.top_transaction()
        if txn:
            txn.rollback()


def _Database_unpickler(db_uid):
    fake_app_obj = sdict(config=sdict(db=sdict()))
    fake_app_obj.config.db.adapter = '<zombie>'
    return Database(fake_app_obj, db_uid=db_uid)


def _Database_pickler(db):
    return _Database_unpickler, (db._db_uid,)


copyreg.pickle(Database, _Database_pickler, _Database_unpickler)
