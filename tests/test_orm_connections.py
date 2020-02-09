# -*- coding: utf-8 -*-
"""
    tests.orm_connections
    ---------------------

    Test pyDAL connection implementation over Emmett.
"""

import pytest

from emmett import App, sdict
from emmett.orm import Database


@pytest.fixture(scope='module')
def db():
    app = App(__name__)
    db = Database(
        app,
        config=sdict(
            uri='sqlite:memory',
            auto_migrate=True,
            auto_connect=False
        )
    )
    return db


def test_connection_ctx_sync(db):
    assert not db._adapter.connection

    with db.connection():
        assert db._adapter.connection

    assert not db._adapter.connection


@pytest.mark.asyncio
async def test_connection_ctx_loop(db):
    assert not db._adapter.connection

    async with db.connection():
        assert db._adapter.connection

    assert not db._adapter.connection
