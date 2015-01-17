# -*- coding: utf-8 -*-
"""
    tests.dal
    ---------

    pyDAL implementation over weppy.

    :copyright: (c) 2015 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

import pytest
from pydal.objects import Table

from weppy import App, sdict
from weppy.dal import DAL, Field, Model, computation, before_insert, \
    after_insert, before_update, after_update, before_delete, after_delete, \
    virtualfield, fieldmethod, modelmethod
from weppy.validators import isntEmpty, notInDb


def _represent_f(value):
    return value


def _widget_f(field, value):
    return value


def _call_bi(fields):
    return fields[:-1]


def _call_ai(fields, id):
    return fields[:-1], id+1


def _call_u(set, fields):
    return set, fields[:-1]


def _call_d(set):
    return set


class TModel(Model):
    tablename = "test"

    fields = [
        Field("a", "string"),
        Field("b"),
        Field("price", "double"),
        Field("quantity", "integer"),
        Field("total", "double"),
        Field("invisible")
    ]

    validators = {
        "a": isntEmpty()
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

    updates = {
        "a": "a_update"
    }

    representation = {
        "a": _represent_f
    }

    widgets = {
        "a": _widget_f
    }

    def setup(self):
        self.entity.b.requires = notInDb(self.db, self.entity.b)

    @computation('total')
    def eval_total(self, row):
        return row.price*row.quantity

    @before_insert
    def bi(self, fields):
        return _call_bi(fields)

    @after_insert
    def ai(self, fields, id):
        return _call_ai(fields, id)

    @before_update
    def bu(self, set, fields):
        return _call_u(set, fields)

    @after_update
    def au(self, set, fields):
        return _call_u(set, fields)

    @before_delete
    def bd(self, set):
        return _call_d(set)

    @after_delete
    def ad(self, set):
        return _call_d(set)

    @virtualfield('totalv')
    def eval_total_v(self, row):
        return row.test.price*row.test.quantity

    @fieldmethod('totalm')
    def eval_total_m(self, row):
        return row.test.price*row.test.quantity

    @modelmethod
    def method_test(db, entity, t):
        return db, entity, t


@pytest.fixture(scope='module')
def db():
    app = App(__name__)
    db = DAL(app)
    db.define_models([TModel])
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
    assert isinstance(db.TModel.a.requires, isntEmpty)


def test_visibility(db):
    assert db.TModel.a.readable is True
    assert db.TModel.a.writable is True
    assert db.TModel.invisible.readable is False
    assert db.TModel.invisible.writable is False


def test_labels(db):
    assert db.TModel.a.label == "A label"


def test_comments(db):
    assert db.TModel.a.comment == "A comment"


def test_updates(db):
    assert db.TModel.a.update == "a_update"


def test_representation(db):
    assert db.TModel.a.represent == _represent_f


def test_widgets(db):
    assert db.TModel.a.widget == _widget_f


def test_set_helper(db):
    assert isinstance(db.TModel.b.requires, notInDb)


def test_computations(db):
    row = sdict(price=12.95, quantity=3)
    rv = db.TModel.total.compute(row)
    assert rv == 12.95*3


def test_callbacks(db):
    fields = ["a", "b", "c"]
    id = 12
    rv = db.TModel._before_insert[-1](fields)
    assert rv == fields[:-1]
    rv = db.TModel._after_insert[-1](fields, id)
    assert rv[0] == fields[:-1] and rv[1] == id+1
    set = {"a": "b"}
    rv = db.TModel._before_update[-1](set, fields)
    assert rv[0] == set and rv[1] == fields[:-1]
    rv = db.TModel._after_update[-1](set, fields)
    assert rv[0] == set and rv[1] == fields[:-1]
    rv = db.TModel._before_delete[-1](set)
    assert rv == set
    rv = db.TModel._after_delete[-1](set)
    assert rv == set


def test_virtualfields(db):
    db.TModel._before_insert = []
    db.TModel._after_insert = []
    db.TModel.insert(a="foo", b="bar", price=12.95, quantity=3)
    db.commit()
    row = db(db.TModel.id > 0).select().first()
    assert row.totalv == 12.95*3


def test_fieldmethods(db):
    row = db(db.TModel.id > 0).select().first()
    assert row.totalm() == 12.95*3


def test_modelmethods(db):
    tm = "foo"
    rv = TModel.method_test(tm)
    assert rv[0] == db and rv[1] == db.TModel and rv[2] == tm
