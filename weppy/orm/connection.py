# -*- coding: utf-8 -*-
"""
    weppy.orm.connection
    --------------------

    Provides pyDAL connection implementation for weppy.

    :copyright: (c) 2014-2018 by Giovanni Barillari

    Parts of this code are inspired to peewee
    :copyright: (c) 2010 by Charles Leifer

    :license: BSD, see LICENSE for more details.
"""

import heapq
import threading
import time
from collections import OrderedDict
from pydal.connection import ConnectionPool
from pydal.helpers.classes import ConnectionConfigurationMixin
from .transactions import _transaction


class ConnectionState(threading.local):
    def __init__(self, **kwargs):
        super(ConnectionState, self).__init__(**kwargs)
        self.reset()

    def reset(self):
        self.closed = True
        self.connection = None
        self.cursors = OrderedDict()
        self.transactions = []

    def set_connection(self, connection):
        self.connection = connection
        self.closed = False


class ConnectionManager(object):
    def __init__(self, adapter, **kwargs):
        self.adapter = adapter
        self.state = ConnectionState()

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
