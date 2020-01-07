# -*- coding: utf-8 -*-
"""
    tests.orm_transactions
    ----------------------

    Test pyDAL transactions implementation over Emmett.
"""

import pytest

from emmett import App, sdict
from emmett.orm import Database, Field, Model


class Register(Model):
    value = Field.int()


@pytest.fixture(scope='module')
def db():
    app = App(__name__)
    db = Database(
        app, config=sdict(
            uri='sqlite:memory', auto_migrate=True, auto_connect=True))
    db.define_models(Register)
    return db


@pytest.fixture(scope='function')
def cleanup(request, db):
    def teardown():
        Register.all().delete()
        db.commit()

    request.addfinalizer(teardown)


def _save(*vals):
    for val in vals:
        Register.create(value=val)


def _values_in_register(*vals):
    db_vals = Register.all().select(orderby=Register.value).column('value')
    return db_vals == list(vals)


def test_transactions(db, cleanup):
    adapter = db._adapter

    assert adapter.in_transaction()

    _save(1)
    db.commit()
    assert _values_in_register(1)

    _save(2)
    db.rollback()
    _save(3)
    with db.atomic():
        _save(4)
        with db.atomic() as sp2:
            _save(5)
            sp2.rollback()
        with db.atomic():
            _save(6)
            with db.atomic() as sp4:
                _save(7)
                with db.atomic():
                    _save(8)
                assert _values_in_register(1, 3, 4, 6, 7, 8)
                sp4.rollback()
            assert _values_in_register(1, 3, 4, 6)
    db.commit()
    assert _values_in_register(1, 3, 4, 6)


def _commit_rollback(db):
    _save(1)
    db.commit()
    _save(2)
    db.rollback()
    assert _values_in_register(1)

    _save(3)
    db.rollback()
    _save(4)
    db.commit()
    assert _values_in_register(1, 4)


def test_commit_rollback(db, cleanup):
    _commit_rollback(db)


def test_commit_rollback_nested(db, cleanup):
    with db.atomic():
        _commit_rollback(db)
    assert _values_in_register(1, 4)


def test_nested_transaction_obj(db, cleanup):
    assert _values_in_register()

    _save(1)
    with db.transaction() as txn:
        _save(2)
        txn.rollback()
        assert _values_in_register()
    _save(3)
    db.commit()
    assert _values_in_register(3)


def test_savepoint_commit(db, cleanup):
    _save(1)
    db.rollback()

    _save(2)
    db.commit()

    with db.atomic() as sp:
        _save(3)
        sp.rollback()
        _save(4)
        sp.commit()

    assert _values_in_register(2, 4)


def text_atomic_exception(db, cleanup):
    def will_fail():
        with db.atomic():
            _save(1)
            _save(None)

    with pytest.raises(Exception):
        will_fail()
    assert _values_in_register()

    def user_error():
        with db.atomic():
            _save(2)
            raise ValueError

    with pytest.raises(ValueError):
        user_error()
    assert _values_in_register()
