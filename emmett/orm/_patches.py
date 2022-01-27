# -*- coding: utf-8 -*-
"""
    emmett.orm._patches
    -------------------

    Provides pyDAL patches.

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

from ..serializers import Serializers
from ..utils import cachedprop

from pydal.adapters.base import BaseAdapter
from pydal.connection import ConnectionPool
from pydal.helpers.classes import ConnectionConfigurationMixin
from pydal.helpers.serializers import Serializers as _Serializers

from .adapters import (
    _initialize,
    _begin,
    _in_transaction,
    _push_transaction,
    _pop_transaction,
    _transaction_depth,
    _top_transaction
)
from .connection import (
    ConnectionManager,
    PooledConnectionManager,
    _connection_init,
    _connect_sync,
    _connect_loop,
    _close_sync,
    _close_loop,
    _connection_getter,
    _connection_setter,
    _cursors_getter,
    _connect_and_configure
)
from .engines.sqlite import SQLite


def _patch_adapter_cls():
    setattr(BaseAdapter, '_initialize_', _initialize)
    setattr(BaseAdapter, 'in_transaction', _in_transaction)
    setattr(BaseAdapter, 'push_transaction', _push_transaction)
    setattr(BaseAdapter, 'pop_transaction', _pop_transaction)
    setattr(BaseAdapter, 'transaction_depth', _transaction_depth)
    setattr(BaseAdapter, 'top_transaction', _top_transaction)
    setattr(BaseAdapter, '_connection_manager_cls', PooledConnectionManager)
    setattr(BaseAdapter, 'begin', _begin)
    setattr(SQLite, '_connection_manager_cls', ConnectionManager)


def _patch_adapter_connection():
    setattr(ConnectionPool, '__init__', _connection_init)
    setattr(ConnectionPool, 'reconnect', _connect_sync)
    setattr(ConnectionPool, 'reconnect_loop', _connect_loop)
    setattr(ConnectionPool, 'close', _close_sync)
    setattr(ConnectionPool, 'close_loop', _close_loop)
    setattr(
        ConnectionPool,
        'connection',
        property(_connection_getter, _connection_setter)
    )
    setattr(ConnectionPool, 'cursors', property(_cursors_getter))
    setattr(
        ConnectionConfigurationMixin,
        '_reconnect_and_configure',
        _connect_and_configure
    )


def _patch_serializers():
    setattr(
        _Serializers,
        'json',
        cachedprop(lambda _: Serializers.get_for('json'), name='json')
    )


_patch_adapter_cls()
_patch_adapter_connection()
_patch_serializers()
