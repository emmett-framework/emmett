# -*- coding: utf-8 -*-
"""
    tests.validators
    ----------------

    Test weppy validators over pyDAL.

    :copyright: (c) 2015 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

import pytest
from weppy import App, sdict
from weppy.dal import DAL, Model, Field
from weppy.validators import isEmptyOr, hasLength, isInt, isFloat, isDate, \
    isTime, isDatetime, isJSON


class A(Model):
    tablename = "a"

    name = Field()
    val = Field('int')
    fval = Field('float')
    text = Field('text')
    password = Field('password')
    d = Field('date')
    t = Field('time')
    dt = Field('datetime')
    json = Field('json')


class AA(Model):
    tablename = "aa"

    a = Field(auto_requires=False)


class AAA(Model):
    tablename = "aaa"
    default_validators = False

    a = Field()


class B(Model):
    tablename = "b"

    a = Field()
    b = Field(requires={'len': {'gte': 5}})

    validators = {
        'a': {'len': {'gte': 5}}
    }


class Len(Model):
    a = Field()
    b = Field()
    c = Field()
    d = Field()

    validators = {
        'a': {'len': 5},
        'b': {'len': {'gt': 4, 'lt': 13}},
        'c': {'len': {'gte': 5, 'lte': 12}},
        'd': {'len': {'range': (5, 13)}}
    }


@pytest.fixture(scope='module')
def db():
    app = App(__name__)
    db = DAL(app, config=sdict(uri='sqlite://validators.db'))
    db.define_models([A, AA, AAA, B, Len])
    return db


def test_defaults(db):
    #: string, text, password
    assert isinstance(db.a.name.requires[0], isEmptyOr)
    assert isinstance(db.a.name.requires[0].other[0], hasLength)
    assert db.a.name.requires[0].other[0].minsize == 0
    assert db.a.name.requires[0].other[0].maxsize == db.a.name.length
    assert isinstance(db.a.text.requires[0].other[0], hasLength)
    assert isinstance(db.a.password.requires[0].other[0], hasLength)
    #: numbers
    assert isinstance(db.a.val.requires[0].other[0], isInt)
    assert isinstance(db.a.fval.requires[0].other[0], isFloat)
    #: date, time, datetime
    assert isinstance(db.a.d.requires[0].other[0], isDate)
    assert isinstance(db.a.t.requires[0].other[0], isTime)
    assert isinstance(db.a.dt.requires[0].other[0], isDatetime)
    #: json
    assert isinstance(db.a.json.requires[0].other[0], isJSON)


def test_defaults_disable(db):
    assert len(db.aa.a.requires) == 0
    assert len(db.aaa.a.requires) == 0


def test_requires_vs_validators(db):
    # using Field(requires=) is the same as 'validators'
    assert db.b.a.requires[0].other[0].minsize == 5
    assert db.b.b.requires[0].other[0].minsize == 5


def test_len(db):
    assert db.Len.a.requires[0].other[0].minsize == 5
    assert db.Len.a.requires[0].other[0].maxsize == 6
    assert db.Len.b.requires[0].other[0].minsize == 5
    assert db.Len.b.requires[0].other[0].maxsize == 13
    assert db.Len.c.requires[0].other[0].minsize == 5
    assert db.Len.c.requires[0].other[0].maxsize == 13
    assert db.Len.d.requires[0].other[0].minsize == 5
    assert db.Len.d.requires[0].other[0].maxsize == 13
