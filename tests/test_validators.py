# -*- coding: utf-8 -*-
"""
    tests.validators
    ----------------

    Test weppy validators over pyDAL.

    :copyright: (c) 2015 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

import pytest
from datetime import datetime, timedelta
from weppy import App, sdict
from weppy.dal import DAL, Model, Field, has_many, belongs_to
from weppy.validators import isEmptyOr, hasLength, isInt, isFloat, isDate, \
    isTime, isDatetime, isJSON, isntEmpty, inSet, inDB, isEmail, isUrl, isIP, \
    isImage, inRange, Equals, Lower, Upper, Cleanup, Urlify, Crypt, notInDB, \
    _allow
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

    a = Field(auto_validation=False)


class AAA(Model):
    tablename = "aaa"
    default_validation = False

    a = Field()


class B(Model):
    tablename = "b"

    a = Field()
    b = Field(validation={'len': {'gte': 5}})

    validation = {
        'a': {'len': {'gte': 5}}
    }


class Consist(Model):
    email = Field()
    url = Field()
    ip = Field()
    image = Field('upload')

    validation = {
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

    validation = {
        'a': {'len': 5},
        'b': {'len': {'gt': 4, 'lt': 13}},
        'c': {'len': {'gte': 5, 'lte': 12}},
        'd': {'len': {'range': (5, 13)}}
    }


class Inside(Model):
    a = Field()
    b = Field('int')

    validation = {
        'a': {'in': ['a', 'b']},
        'b': {'in': {'range': (1, 5)}}
    }


class Num(Model):
    a = Field('int')
    b = Field('int')
    c = Field('int')

    validation = {
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

    validation = {
        'a': {'lower': True},
        'b': {'upper': True},
        'c': {'clean': True},
        'd': {'urlify': True},
        'e': {'len': {'range': (6, 25)}, 'crypt': True},
        'f': {'len': {'gt': 5, 'lt': 25}, 'crypt': 'md5'}
    }


class Eq(Model):
    a = Field()
    b = Field('int')
    c = Field('float')

    validation = {
        'a': {'equals': 'asd'},
        'b': {'equals': 2},
        'c': {'not': {'equals': 2.4}}
    }


class Person(Model):
    has_many('things')

    name = Field(validation={'empty': False})
    surname = Field(validation={'presence': True})


class Thing(Model):
    belongs_to('person')

    name = Field()
    color = Field()
    uid = Field(unique=True)

    validation = {
        'name': {'presence': True},
        'color': {'in': ['blue', 'red']},
        'uid': {'empty': False}
    }


class Allowed(Model):
    a = Field(validation={'in': ['a', 'b'], 'allow': None})
    b = Field(validation={'in': ['a', 'b'], 'allow': 'empty'})
    c = Field(validation={'in': ['a', 'b'], 'allow': 'blank'})


class Mixed(Model):
    belongs_to('person')

    date = Field('date')
    type = Field()
    inside = Field()
    number = Field('int')
    dont = Field()
    yep = Field()
    psw = Field('password')

    validation = {
        'date': {'format': '%d/%m/%Y', 'gt': lambda: datetime.utcnow().date()},
        'type': {'in': ['a', 'b'], 'allow': None},
        'inside': {'in': ['asd', 'lol']},
        'number': {'allow': 'blank'},
        'dont': {'empty': True},
        'yep': {'presence': True},
        'psw': {'len': {'range': (6, 25)}, 'crypt': True}
    }


@pytest.fixture(scope='module')
def db():
    app = App(__name__)
    db = DAL(app, config=sdict(uri='sqlite://validators.db'))
    db.define_models([
        A, AA, AAA, B, Consist, Len, Inside, Num, Eq, Proc, Person, Thing,
        Allowed, Mixed
    ])
    return db


def test_defaults(db):
    #: string, text, password
    assert isinstance(db.a.name.requires[0], hasLength)
    assert db.a.name.requires[0].minsize == 0
    assert db.a.name.requires[0].maxsize == db.a.name.length
    assert isinstance(db.a.text.requires[0], hasLength)
    assert isinstance(db.a.password.requires[0], hasLength)
    #: numbers
    assert isinstance(db.a.val.requires[0], isInt)
    assert isinstance(db.a.fval.requires[0], isFloat)
    #: date, time, datetime
    assert isinstance(db.a.d.requires[0], isDate)
    assert isinstance(db.a.t.requires[0], isTime)
    assert isinstance(db.a.dt.requires[0], isDatetime)
    #: json
    assert isinstance(db.a.json.requires[0], isJSON)


def test_defaults_disable(db):
    assert len(db.aa.a.requires) == 0
    assert len(db.aaa.a.requires) == 0


def test_requires_vs_validators(db):
    # using Field(validation=) is the same as 'validators'
    assert db.b.a.requires[0].minsize == 5
    assert db.b.b.requires[0].minsize == 5


def test_is(db):
    assert isinstance(Consist.email.requires[0], isEmail)
    assert isinstance(Consist.url.requires[0], isUrl)
    assert isinstance(Consist.ip.requires[0], isIP)
    assert isinstance(Consist.image.requires[0], isImage)


def test_len(db):
    assert Len.a.requires[0].minsize == 5
    assert Len.a.requires[0].maxsize == 6
    assert Len.a.requires[0].inc[0] is True
    assert Len.a.requires[0].inc[1] is False
    assert Len.b.requires[0].minsize == 4
    assert Len.b.requires[0].maxsize == 13
    assert Len.b.requires[0].inc[0] is False
    assert Len.b.requires[0].inc[1] is False
    assert Len.c.requires[0].minsize == 5
    assert Len.c.requires[0].maxsize == 12
    assert Len.c.requires[0].inc[0] is True
    assert Len.c.requires[0].inc[1] is True
    assert Len.d.requires[0].minsize == 5
    assert Len.d.requires[0].maxsize == 13
    assert Len.d.requires[0].inc[0] is True
    assert Len.d.requires[0].inc[1] is False


def test_in(db):
    assert isinstance(Inside.a.requires[1], inSet)
    assert isinstance(Inside.b.requires[1], inRange)


def test_numerical(db):
    assert Num.a.requires[1].minimum == 0
    assert Num.b.requires[1].maximum == 5
    assert Num.a.requires[1].inc[0] is False
    assert Num.c.requires[1].minimum == 0
    assert Num.c.requires[1].maximum == 4
    assert Num.c.requires[1].inc[1] is True


def test_eq(db):
    assert isinstance(Eq.a.requires[1], Equals)
    assert isinstance(Eq.b.requires[1], Equals)
    assert isinstance(Eq.c.requires[1], _not)
    assert isinstance(Eq.c.requires[1].conditions[0], Equals)


def test_processors(db):
    assert isinstance(Proc.a.requires[1], Lower)
    assert isinstance(Proc.b.requires[1], Upper)
    assert isinstance(Proc.c.requires[1], Cleanup)
    assert isinstance(Proc.d.requires[1], Urlify)
    assert isinstance(Proc.e.requires[1], Crypt)
    assert isinstance(Proc.f.requires[1], Crypt)


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
    assert len(Thing.color.requires) == 2
    assert isinstance(Thing.color.requires[0], hasLength)
    assert isinstance(Thing.color.requires[1], inSet)
    assert isinstance(Thing.person.requires[1], inDB)


def test_unique(db):
    assert isinstance(Thing.uid.requires[2], notInDB)


def test_allow(db):
    assert isinstance(Allowed.a.requires[0], _allow)
    assert isinstance(Allowed.b.requires[0], isEmptyOr)
    assert isinstance(Allowed.c.requires[0], isEmptyOr)
    assert isinstance(Allowed.a.requires[0].conditions[1], inSet)
    assert isinstance(Allowed.b.requires[0].other[1], inSet)
    assert isinstance(Allowed.c.requires[0].other[1], inSet)


def test_validation(db):
    #: 'is'
    #: 'len'
    #: 'in'
    #: 'gt', 'lt', 'gte', 'lte'
    #: 'equals'
    #: 'not'
    #: 'match'
    #: 'allow'
    #: processing validators
    #: 'presence'
    mario = {'name': 'mario'}
    errors = Person.validate(mario)
    assert 'surname' in errors
    assert len(errors) == 1
    #: 'presence' with reference, 'unique'
    thing = {'name': 'a', 'person': 5, 'color': 'blue', 'uid': 'lol'}
    errors = Thing.validate(thing)
    assert 'person' in errors
    assert len(errors) == 1
    mario = {'name': 'mario', 'surname': 'draghi'}
    mario = Person.create(mario)
    assert len(mario.errors) == 0
    assert mario.id == 1
    thing = {'name': 'euro', 'person': mario.id, 'color': 'red', 'uid': 'lol'}
    thing = Thing.create(thing)
    assert len(thing.errors) == 0
    thing = {'name': 'euro2', 'person': mario.id, 'color': 'red', 'uid': 'lol'}
    errors = Thing.validate(thing)
    assert len(errors) == 1
    assert 'uid' in errors


def test_multi(db):
    from weppy.globals import current
    current._language = 'en'
    p = db.Person(name="mario")
    base_data = {
        'date': '{0:%d/%m/%Y}'.format(datetime.utcnow()+timedelta(days=1)),
        'type': 'a',
        'inside': 'asd',
        'number': 1,
        'yep': 'asd',
        'psw': 'password',
        'person': p.id
    }
    #: everything ok
    res = Mixed.create(base_data)
    assert res.id == 1
    assert len(res.errors) == 0
    #: invalid belongs
    vals = dict(base_data)
    del vals['person']
    res = Mixed.create(vals)
    assert res.id is None
    assert len(res.errors) == 1
    assert 'person' in res.errors
    #: invalid date range
    vals = dict(base_data)
    vals['date'] = '{0:%d/%m/%Y}'.format(datetime.utcnow()-timedelta(days=2))
    res = Mixed.create(vals)
    assert res.id is None
    assert len(res.errors) == 1
    assert 'date' in res.errors
    #: invalid date format
    vals['date'] = '76-12-1249'
    res = Mixed.create(vals)
    assert res.id is None
    assert len(res.errors) == 1
    assert 'date' in res.errors
    #: invalid in
    vals = dict(base_data)
    vals['type'] = ' '
    res = Mixed.create(vals)
    assert res.id is None
    assert len(res.errors) == 1
    assert 'type' in res.errors
    #: empty number
    vals = dict(base_data)
    vals['number'] = None
    res = Mixed.create(vals)
    assert res.id == 2
    assert len(res.errors) == 0
    #: invalid number
    vals = dict(base_data)
    vals['number'] = 'asd'
    res = Mixed.create(vals)
    assert res.id is None
    assert len(res.errors) == 1
    assert 'number' in res.errors
    #: invalid empty
    vals = dict(base_data)
    vals['dont'] = '2'
    res = Mixed.create(vals)
    assert res.id is None
    assert len(res.errors) == 1
    assert 'dont' in res.errors
    #: invalid presence
    vals = dict(base_data)
    vals['yep'] = ''
    res = Mixed.create(vals)
    assert res.id is None
    assert len(res.errors) == 1
    assert 'yep' in res.errors
    #: invalid password
    vals = dict(base_data)
    vals['psw'] = ''
    res = Mixed.create(vals)
    assert res.id is None
    assert len(res.errors) == 1
    assert 'psw' in res.errors
    vals['psw'] = 'aksjfalsdkjflkasjdflkajsldkjfalslkdfjaslkdjf'
    res = Mixed.create(vals)
    assert res.id is None
    assert len(res.errors) == 1
    assert 'psw' in res.errors
