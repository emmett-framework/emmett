# -*- coding: utf-8 -*-
"""
    emmett.orm.connection
    ---------------------

    Provides pyDAL connection implementation for Emmett.

    :copyright: 2014 Giovanni Barillari

    Parts of this code are inspired to peewee
    :copyright: (c) 2010 by Charles Leifer

    :license: BSD-3-Clause
"""

import contextvars
import heapq
import threading
import time

from collections import OrderedDict
from pydal.connection import ConnectionPool
from pydal.helpers.classes import ConnectionConfigurationMixin

from ..ctx import current
from .transactions import _transaction


class ConnectionStateCtxVars(object):
    __slots__ = ('_connection', '_transactions', '_cursors', '_closed')

    def __init__(self):
        self._connection = contextvars.ContextVar('_emt_orm_cs_connection')
        self._transactions = contextvars.ContextVar('_emt_orm_cs_transactions')
        self._cursors = contextvars.ContextVar('_emt_orm_cs_cursors')
        self._closed = contextvars.ContextVar('_emt_orm_cs_closed')
        self.reset()

    @property
    def connection(self):
        return self._connection.get()

    @property
    def transactions(self):
        return self._transactions.get()

    @property
    def cursors(self):
        return self._cursors.get()

    @property
    def closed(self):
        return self._closed.get()

    def __set(self, connection, closed):
        self._connection.set(connection)
        self._transactions.set([])
        self._cursors.set(OrderedDict())
        self._closed.set(closed)

    def set_connection(self, connection):
        self.__set(connection, False)

    def reset(self):
        self.__set(None, True)


class ConnectionState(object):
    __slots__ = ('_connection', '_transactions', '_cursors', '_closed')

    def __init__(self, connection=None):
        self.connection = connection
        self._transactions = []
        self._cursors = OrderedDict()

    @property
    def connection(self):
        return self._connection

    @connection.setter
    def connection(self, value):
        self._connection = value
        self._closed = not bool(value)


class ConnectionStateCtl(object):
    __slots__ = ['_state_obj_var', '_state_load_var']

    state_cls = ConnectionState

    def __init__(self):
        inst_id = id(self)
        self._state_obj_var = f'__emt_orm_state_{inst_id}__'
        self._state_load_var = f'__emt_orm_state_loaded_{inst_id}__'

    @property
    def _has_ctx(self):
        return getattr(current, self._state_load_var, False)

    @property
    def ctx(self):
        if not self._has_ctx:
            setattr(current, self._state_obj_var, self.__class__.state_cls())
            setattr(current, self._state_load_var, True)
        return getattr(current, self._state_obj_var)

    @property
    def connection(self):
        return self.ctx.connection

    @property
    def transactions(self):
        return self.ctx._transactions

    @property
    def cursors(self):
        return self.ctx._cursors

    @property
    def closed(self):
        return self.ctx._closed

    def set_connection(self, connection):
        self.ctx.connection = connection

    def reset(self):
        self.ctx.connection = None
        self.ctx._transactions = []
        self.ctx._cursors = OrderedDict()


class ConnectionManager(object):
    state_cls = ConnectionStateCtl

    def __init__(self, adapter, **kwargs):
        self.adapter = adapter
        self.state = self.__class__.state_cls()

    def configure(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def connect(self):
        return self.adapter.connector(), True

    def close(self, connection, *args, **kwargs):
        connection.close()


class PooledConnectionManager(ConnectionManager):
    def __init__(self, adapter, max_connections=5, stale_timeout=0):
        super(PooledConnectionManager, self).__init__(adapter)
        self.max_connections = max_connections
        self.stale_timeout = stale_timeout
        self.connections = []
        self.in_use = {}
        self._lock = threading.RLock()

    def is_stale(self, timestamp):
        return (time.time() - timestamp) > self.stale_timeout

    def connect(self):
        _opened = False
        while True:
            try:
                with self._lock:
                    ts, conn = heapq.heappop(self.connections)
                key = id(conn)
            except IndexError:
                ts = conn = None
                break
            else:
                if self.stale_timeout and self.is_stale(ts):
                    try:
                        super(PooledConnectionManager, self).close(conn)
                    finally:
                        ts = conn = None
                else:
                    break
        if conn is None:
            if self.max_connections and (
                len(self.in_use) >= self.max_connections
            ):
                raise RuntimeError('Exceeded maximum connections.')
            conn, _opened = super(PooledConnectionManager, self).connect()
            ts = time.time()
            key = id(conn)
        self.in_use[key] = ts
        return conn, _opened

    def can_reuse(self, connection):
        return True

    def close(self, connection, close_connection=False):
        key = id(connection)
        ts = self.in_use.pop(key)
        if close_connection:
            super(PooledConnectionManager, self).close(connection)
        else:
            if self.stale_timeout and self.is_stale(ts):
                super(PooledConnectionManager, self).close(connection)
            elif self.can_reuse(connection):
                with self._lock:
                    heapq.heappush(self.connections, (ts, connection))

    def close_all(self):
        for _, connection in self.connections:
            self.close(connection, close_connection=True)


def _init(self, *args, **kwargs):
    self._connection_manager = self._connection_manager_cls(self)


def _connect(self, with_transaction=True, reuse_if_open=False):
    if not self._connection_manager.state.closed:
        if reuse_if_open:
            return False
        raise RuntimeError('Connection already opened.')
    self.connection, _opened = self._connection_manager.connect()
    if _opened:
        self.after_connection_hook()
    if with_transaction:
        txn = _transaction(self)
        txn.__enter__()
    return True


def _close(self, action='commit', really=True):
    is_open = not self._connection_manager.state.closed
    if not is_open:
        return is_open
    if self.transaction_depth() == 1:
        txn = self.top_transaction()
        try:
            txn.__exit__(None, None, None)
            succeeded = True
        except Exception:
            succeeded = False
        really = not succeeded
    try:
        self._connection_manager.close(self.connection, really)
    finally:
        self.connection = None
    return is_open


def _connection_getter(self):
    return self._connection_manager.state.connection


def _connection_setter(self, connection):
    if connection is None:
        self._connection_manager.state.reset()
        return
    self._connection_manager.state.set_connection(connection)


def _cursors_getter(self):
    return self._connection_manager.state.cursors


def _connect_and_configure(self, *args, **kwargs):
    self._connection_reconnect(*args, **kwargs)
    with self._reconnect_lock:
        if self._reconnect_mocked:
            self._configure_on_first_reconnect()
            self.reconnect = self._connection_reconnect
            self._reconnect_mocked = False


def _patch_adapter_connection():
    setattr(ConnectionPool, '__init__', _init)
    setattr(ConnectionPool, 'reconnect', _connect)
    setattr(ConnectionPool, 'close', _close)
    setattr(
        ConnectionPool, 'connection',
        property(_connection_getter, _connection_setter))
    setattr(ConnectionPool, 'cursors', property(_cursors_getter))
    setattr(
        ConnectionConfigurationMixin, '_reconnect_and_configure',
        _connect_and_configure)
