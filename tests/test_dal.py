# -*- coding: utf-8 -*-
"""
    tests.dal
    ---------

    pyDAL implementation over weppy.

    :copyright: (c) 2014 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

import pytest
from weppy import App
from weppy.dal import DAL, ModelsDAL, Field
from weppy.dal.objects import Table
from weppy.dal.models import Model, AuthModel
from weppy.validators import IS_NOT_EMPTY


class TModel(Model):
    tablename = "test"

    fields = [
        Field("a", "string"),
        Field("invisible")
    ]

    validators = {
        "a": IS_NOT_EMPTY()
    }

    visibility = {
        "invisible": (False, False)
    }

    labels = {
        "a": "A label"
    }

    comments = {
        "a": "A comment"
    }


@pytest.fixture
def db():
    app = App(__name__)
    db = ModelsDAL(app)
    db.define_datamodels([TModel])
    return db


def test_db_instance(db):
    assert isinstance(db, DAL)


def test_table_definition(db):
    assert isinstance(db.TModel, Table)
    assert isinstance(db[TModel.tablename], Table)


def test_fields(db):
    assert isinstance(db.TModel.a, Field)
    assert db.TModel.a.type == "string"


def test_validators(db):
    assert isinstance(db.TModel.a.requires, IS_NOT_EMPTY)


def test_visibility(db):
    assert db.TModel.a.readable is True
    assert db.TModel.a.writable is True
    assert db.TModel.invisible.readable is False
    assert db.TModel.invisible.writable is False


def test_labels(db):
    assert db.TModel.a.label == "A label"


def test_comments(db):
    assert db.TModel.a.comment == "A comment"


def test_updates():
    pass


def test_representation():
    pass


def test_widgets():
    pass


def test_set_helper():
    pass


def test_computations():
    pass


def test_callbacks():
    pass


def test_virtualfields():
    pass


def test_fieldmethods():
    pass


def test_modelmethods():
    pass
