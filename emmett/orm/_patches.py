# -*- coding: utf-8 -*-
"""
emmett.orm._patches
-------------------

Provides pyDAL patches.

:copyright: 2014 Giovanni Barillari
:license: BSD-3-Clause
"""

from emmett_core.utils import cachedprop
from pydal.adapters.base import BaseAdapter
from pydal.connection import ConnectionPool
from pydal.helpers.classes import ConnectionConfigurationMixin
from pydal.helpers.serializers import Serializers as _Serializers

from ..serializers import Serializers
from .adapters import (
    _begin,
    _in_transaction,
    _initialize,
    _pop_transaction,
    _push_transaction,
    _top_transaction,
    _transaction_depth,
)
from .connection import (
    PooledConnectionManager,
    _close_loop,
    _close_sync,
    _connect_and_configure,
    _connect_loop,
    _connect_sync,
    _connection_getter,
    _connection_init,
    _connection_setter,
    _cursors_getter,
)


def _patch_adapter_cls():
    BaseAdapter._initialize_ = _initialize
    BaseAdapter.in_transaction = _in_transaction
    BaseAdapter.push_transaction = _push_transaction
    BaseAdapter.pop_transaction = _pop_transaction
    BaseAdapter.transaction_depth = _transaction_depth
    BaseAdapter.top_transaction = _top_transaction
    BaseAdapter._connection_manager_cls = PooledConnectionManager
    BaseAdapter.begin = _begin


def _patch_adapter_connection():
    ConnectionPool.__init__ = _connection_init
    ConnectionPool.reconnect = _connect_sync
    ConnectionPool.reconnect_loop = _connect_loop
    ConnectionPool.close = _close_sync
    ConnectionPool.close_loop = _close_loop
    ConnectionPool.connection = property(_connection_getter, _connection_setter)
    ConnectionPool.cursors = property(_cursors_getter)
    ConnectionConfigurationMixin._reconnect_and_configure = _connect_and_configure


def _patch_serializers():
    _Serializers.json = cachedprop(lambda _: Serializers.get_for("json"), name="json")


_patch_adapter_cls()
_patch_adapter_connection()
_patch_serializers()
