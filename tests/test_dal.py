# -*- coding: utf-8 -*-
"""
    tests.dal
    ---------

    pyDAL implementation over weppy.

    :copyright: (c) 2014 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

from weppy import App
from weppy.dal import DAL, ModelsDAL, Field
from weppy.dal.objects import Table
from weppy.dal.models import Model, AuthModel
from weppy.validators import IS_NOT_EMPTY


class TestModel(Model):
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


def _init_db():
    app = App(__name__)
    db = ModelsDAL(app)
    return db


def test_db_instance():
    db = _init_db()
    assert isinstance(db, DAL)


def test_table_definition():
    db = _init_db()
    db.define_datamodels([TestModel])
    assert isinstance(db.TestModel, Table)
    assert isinstance(db[TestModel.tablename], Table)


def test_fields():
    db = _init_db()
    db.define_datamodels([TestModel])
    assert isinstance(db.TestModel.a, Field)
    # type string


def test_validators():
    db = _init_db()
    db.define_datamodels([TestModel])
    assert isinstance(db.TestModel.a.requires, IS_NOT_EMPTY)


def test_visibility():
    db = _init_db()
    db.define_datamodels([TestModel])
    assert db.TestModel.a.readable is True
    assert db.TestModel.a.writable is True
    assert db.TestModel.invisible.readable is False
    assert db.TestModel.invisible.writable is False


def test_labels():
    pass


def test_comments():
    pass


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
