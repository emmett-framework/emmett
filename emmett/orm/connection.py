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

import asyncio
import contextvars
import heapq
import threading
import time

from collections import OrderedDict
from functools import partial

from ..ctx import current
from ..utils import cachedprop
from .errors import MaxConnectionsExceeded
from .transactions import _transaction


class ConnectionStateCtxVars:
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


class ConnectionState:
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


class ConnectionStateCtl:
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


class ConnectionManager:
    __slots__ = ['adapter', 'state', '__dict__']
    state_cls = ConnectionStateCtl

    def __init__(self, adapter, **kwargs):
        self.adapter = adapter
        self.state = self.__class__.state_cls()

    def configure(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    @cachedprop
    def _loop(self):
        return asyncio.get_running_loop()

    def _connector_sync(self):
        return self.adapter.connector()

    _connector_loop = _connector_sync

    def _connection_open_sync(self):
        return self._connector_sync(), True

    async def _connection_open_loop(self):
        return (
            await self._loop.run_in_executor(
                None, self._connector_loop
            ),
            True
        )

    def _connection_close_sync(self, connection, *args, **kwargs):
        try:
            connection.close()
        except Exception:
            pass

    async def _connection_close_loop(self, connection, *args, **kwargs):
        return await self._loop.run_in_executor(
            None, partial(self._connection_close_sync, connection)
        )

    connect_sync = _connection_open_sync
    connect_loop = _connection_open_loop

    disconnect_sync = _connection_close_sync
    disconnect_loop = _connection_close_loop

    def __del__(self):
        if not self.state.closed:
            self.disconnect_sync(self.state.connection)


class PooledConnectionManager(ConnectionManager):
    __slots__ = [
        'max_connections', 'connect_timeout', 'stale_timeout',
        'connections_map', 'connections_sync',
        'in_use', '_lock_sync'
    ]

    def __init__(
        self,
        adapter,
        max_connections=5,
        connect_timeout=0,
        stale_timeout=0
    ):
        super().__init__(adapter)
        self.max_connections = max(max_connections, 1)
        self.connect_timeout = connect_timeout
        self.stale_timeout = stale_timeout
        self.connections_map = {}
        self.connections_sync = []
        self.in_use = {}
        self._lock_sync = threading.RLock()

    @cachedprop
    def _lock_loop(self):
        return asyncio.Lock()

    @cachedprop
    def connections_loop(self):
        return asyncio.LifoQueue()

    def is_stale(self, timestamp):
        return (time.time() - timestamp) > self.stale_timeout

    def connect_sync(self):
        if not self.connect_timeout:
            return self._acquire_sync()
        expires = time.time() + self.connect_timeout
        while time.time() < expires:
            try:
                rv = self._acquire_sync()
            except MaxConnectionsExceeded:
                time.sleep(0.1)
            else:
                return rv
        raise MaxConnectionsExceeded()

    async def connect_loop(self):
        return await asyncio.wait_for(
            self._acquire_loop(), self.connect_timeout or None
        )

    def _acquire_sync(self):
        _opened = False
        while True:
            try:
                with self._lock_sync:
                    ts, key = heapq.heappop(self.connections_sync)
            except IndexError:
                ts = key = conn = None
                break
            else:
                if self.stale_timeout and self.is_stale(ts):
                    self._connection_close_sync(self.connections_map.pop(key))
                else:
                    conn = self.connections_map[key]
                    break
        if conn is None:
            if len(self.connections_map) >= self.max_connections:
                raise MaxConnectionsExceeded()
            conn, _opened = self._connection_open_sync()
            ts, key = time.time(), id(conn)
            self.connections_map[key] = conn
        self.in_use[key] = ts
        return conn, _opened

    async def _acquire_loop(self):
        _opened = False
        while True:
            if len(self.connections_map) < self.max_connections:
                async with self._lock_loop:
                    if len(self.connections_map) < self.max_connections:
                        conn, _opened = await self._connection_open_loop()
                        ts, key = time.time(), id(conn)
                        self.connections_map[key] = conn
                        break
            ts, key = await self.connections_loop.get()
            if self.stale_timeout and self.is_stale(ts):
                await self._connection_close_loop(
                    self.connections_map.pop(key)
                )
            else:
                conn = self.connections_map[key]
                break
        self.in_use[key] = ts
        return conn, _opened

    def disconnect_sync(self, connection, close_connection=False):
        key = id(connection)
        ts = self.in_use.pop(key)
        if close_connection:
            self.connections_map.pop(key)
            self._connection_close_sync(connection)
        else:
            if self.stale_timeout and self.is_stale(ts):
                self.connections_map.pop(key)
                self._connection_close_sync(connection)
            else:
                with self._lock_sync:
                    heapq.heappush(self.connections_sync, (ts, key))

    async def disconnect_loop(self, connection, close_connection=False):
        key = id(connection)
        ts = self.in_use.pop(key)
        if close_connection:
            self.connections_map.pop(key)
            await self._connection_close_loop(connection)
        else:
            if self.stale_timeout and self.is_stale(ts):
                self.connections_map.pop(key)
                await self._connection_close_loop(connection)
            else:
                self.connections_loop.put_nowait((ts, key))

    def disconnect_all(self):
        for connection in self.connections_map.values():
            self.disconnect_sync(connection, close_connection=True)

    def __del__(self):
        self.disconnect_all()


def _connection_init(self, *args, **kwargs):
    self._connection_manager = self._connection_manager_cls(self)


def _connect_sync(self, with_transaction=True, reuse_if_open=False):
    if not self._connection_manager.state.closed:
        if reuse_if_open:
            return False
        raise RuntimeError('Connection already opened.')
    self.connection, _opened = self._connection_manager.connect_sync()
    if _opened:
        self.after_connection_hook()
    if with_transaction:
        txn = _transaction(self)
        txn.__enter__()
    return True


async def _connect_loop(self, with_transaction=True, reuse_if_open=False):
    if not self._connection_manager.state.closed:
        if reuse_if_open:
            return False
        raise RuntimeError('Connection already opened.')
    self.connection, _opened = await self._connection_manager.connect_loop()
    if _opened:
        self.after_connection_hook()
    if with_transaction:
        txn = _transaction(self)
        txn.__enter__()
    return True


def _close_sync(self, action='commit', really=True):
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
        self._connection_manager.disconnect_sync(self.connection, really)
    finally:
        self.connection = None
    return is_open


async def _close_loop(self, action='commit', really=True):
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
        await self._connection_manager.disconnect_loop(self.connection, really)
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
