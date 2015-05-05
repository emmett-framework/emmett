# -*- coding: utf-8 -*-
"""
    tests.validators
    ----------------

    Test weppy validators over pyDAL.

    :copyright: (c) 2015 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

import pytest
from weppy import App
from weppy.dal import DAL, Model, Field
from weppy.validators import isEmptyOr, hasLength, isInt, isFloat, isDate, \
    isTime, isDatetime, isJSON


class A(Model):
    name = Field()
    val = Field('int')
    fval = Field('float')
    text = Field('text')
    password = Field('password')
    d = Field('date')
    t = Field('time')
    dt = Field('datetime')
    json = Field('json')


@pytest.fixture(scope='module')
def db():
    app = App(__name__)
    db = DAL(app)
    db.define_models([A])
    return db


def test_defaults(db):
    #: string, text, password
    assert isinstance(db.name.requires[0], isEmptyOr)
    assert isinstance(db.name.requires[0].other[0], hasLength)
    assert db.name.requires[0].other[0].minsize == 0
    assert db.name.requires[0].other[0].maxsize == 255
    assert isinstance(db.text.requires[0].other[0], hasLength)
    assert isinstance(db.password.requires[0].other[0], hasLength)
    #: numbers
    assert isinstance(db.val.requires[0].other[0], isInt)
    assert isinstance(db.fval.requires[0].other[0], isFloat)
    #: date, time, datetime
    assert isinstance(db.d.requires[0].other[0], isDate)
    assert isinstance(db.t.requires[0].other[0], isTime)
    assert isinstance(db.dt.requires[0].other[0], isDatetime)
    #: json
    assert isinstance(db.json.requires[0].other[0], isJSON)
