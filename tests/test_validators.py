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
from weppy.dal import DAL, Model, Field, has_many, belongs_to
from weppy.validators import isEmptyOr, hasLength, isInt, isFloat, isDate, \
    isTime, isDatetime, isJSON, isntEmpty, inSet, inDb, isEmail, isUrl, isIP, \
    isImage, inRange, Equals, Lower, Upper, Cleanup, Slug, Crypt
from weppy.validators.basic import _not


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


class Consist(Model):
    email = Field()
    url = Field()
    ip = Field()
    image = Field('upload')

    validators = {
        'email': {'is': 'email'},
        'url': {'is': 'url'},
        'ip': {'is': 'ip'},
        'image': {'is': 'image'}
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


class Inside(Model):
    a = Field()
    b = Field('int')

    validators = {
        'a': {'in': ['a', 'b']},
        'b': {'in': {'range': (1, 5)}}
    }


class Num(Model):
    a = Field('int')
    b = Field('int')
    c = Field('int')

    validators = {
        'a': {'gt': 0},
        'b': {'lt': 5},
        'c': {'gt': 0, 'lte': 4}
    }


class Proc(Model):
    a = Field()
    b = Field()
    c = Field()
    d = Field()
    e = Field('password')
    f = Field('password')

    validators = {
        'a': {'lower': True},
        'b': {'upper': True},
        'c': {'clean': True},
        'd': {'slug': True},
        'e': {'len': {'range': (6, 25)}, 'crypt': True},
        'f': {'len': {'gt': 5, 'lt': 25}, 'crypt': 'md5'}
    }


class Eq(Model):
    a = Field()
    b = Field('int')
    c = Field('float')

    validators = {
        'a': {'equals': 'asd'},
        'b': {'equals': 2},
        'c': {'not': {'equals': 2.4}}
    }


class Person(Model):
    has_many('things')

    name = Field(requires={'empty': False})
    surname = Field(requires={'presence': True})


class Thing(Model):
    belongs_to('person')

    name = Field()
    color = Field()

    validators = {
        'name': {'presence': True},
        'color': {'empty': False, 'in': ['blue', 'red']}
    }


@pytest.fixture(scope='module')
def db():
    app = App(__name__)
    db = DAL(app, config=sdict(uri='sqlite://validators.db'))
    db.define_models([
        A, AA, AAA, B, Consist, Len, Inside, Num, Eq, Proc, Person, Thing
    ])
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


def test_is(db):
    assert isinstance(Consist.email.requires[0].other[0], isEmail)
    assert isinstance(Consist.url.requires[0].other[0], isUrl)
    assert isinstance(Consist.ip.requires[0].other[0], isIP)
    assert isinstance(Consist.image.requires[0].other[0], isImage)


def test_len(db):
    assert Len.a.requires[0].other[0].minsize == 5
    assert Len.a.requires[0].other[0].maxsize == 6
    assert Len.b.requires[0].other[0].minsize == 5
    assert Len.b.requires[0].other[0].maxsize == 13
    assert Len.c.requires[0].other[0].minsize == 5
    assert Len.c.requires[0].other[0].maxsize == 13
    assert Len.d.requires[0].other[0].minsize == 5
    assert Len.d.requires[0].other[0].maxsize == 13


def test_in(db):
    assert isinstance(Inside.a.requires[0].other[0], inSet)
    assert isinstance(Inside.b.requires[0].other[0], inRange)


def test_numerical(db):
    assert Num.a.requires[0].other[0].minimum == 1
    assert Num.b.requires[0].other[0].maximum == 5
    assert Num.c.requires[0].other[0].minimum == 1
    assert Num.c.requires[0].other[0].maximum == 5


def test_eq(db):
    assert isinstance(Eq.a.requires[0].other[0], Equals)
    assert isinstance(Eq.a.requires[0].other[0], _not)
    assert isinstance(Eq.a.requires[0].other[0].conditions[0], Equals)


def test_processors(db):
    assert isinstance(Proc.a.requires[0].other[0], Lower)
    assert isinstance(Proc.b.requires[0].other[0], Upper)
    assert isinstance(Proc.c.requires[0].other[0], Cleanup)
    assert isinstance(Proc.d.requires[0].other[0], Slug)
    assert isinstance(Proc.e.requires[0].other[1], Crypt)
    assert isinstance(Proc.f.requires[0].other[1], Crypt)


def test_presence(db):
    assert len(Person.name.requires) == 2
    assert isinstance(Person.name.requires[0], isntEmpty)
    assert isinstance(Person.name.requires[1], hasLength)
    assert len(Person.surname.requires) == 2
    assert isinstance(Person.surname.requires[0], isntEmpty)
    assert isinstance(Person.surname.requires[1], hasLength)
    assert len(Thing.name.requires) == 2
    assert isinstance(Thing.name.requires[0], isntEmpty)
    assert isinstance(Thing.name.requires[1], hasLength)
    assert len(Thing.color.requires) == 3
    assert isinstance(Thing.color.requires[0], isntEmpty)
    assert isinstance(Thing.color.requires[1], hasLength)
    assert isinstance(Thing.color.requires[2], inSet)
    #assert isinstance(Thing.person.requires[0], inDb)
