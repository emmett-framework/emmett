# -*- coding: utf-8 -*-
"""
    tests.orm
    ---------

    Test pyDAL implementation over Emmett.
"""

import pytest

from datetime import datetime, timedelta
from pydal.objects import Table
from pydal import Field as _Field
from emmett import App, sdict
from emmett.orm import (
    Database, Field, Model,
    compute,
    before_insert, after_insert,
    before_update, after_update,
    before_delete, after_delete,
    rowattr, rowmethod,
    has_one, has_many, belongs_to,
    scope
)
from emmett.validators import isntEmpty, hasLength


def _represent_f(value):
    return value


def _widget_f(field, value):
    return value


def _call_bi(fields):
    return fields[:-1]


def _call_ai(fields, id):
    return fields[:-1], id + 1


def _call_u(set, fields):
    return set, fields[:-1]


def _call_d(set):
    return set


class Stuff(Model):
    a = Field.string()
    b = Field()
    price = Field.float()
    quantity = Field.int()
    total = Field.float()
    invisible = Field()

    validation = {
        "a": {'presence': True}
    }

    fields_rw = {
        "invisible": False
    }

    form_labels = {
        "a": "A label"
    }

    form_info = {
        "a": "A comment"
    }

    update_values = {
        "a": "a_update"
    }

    repr_values = {
        "a": _represent_f
    }

    form_widgets = {
        "a": _widget_f
    }

    # def setup(self):
    #     self.table.b.requires = notInDb(self.db, self.table.b)

    @compute('total')
    def eval_total(self, row):
        return row.price * row.quantity

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

    @rowattr('totalv')
    def eval_total_v(self, row):
        return row.price * row.quantity

    @rowmethod('totalm')
    def eval_total_m(self, row):
        return row.price * row.quantity

    @classmethod
    def method_test(cls, t):
        return cls.db, cls.table, t


class Person(Model):
    has_many(
        'things', {'features': {'via': 'things'}}, {'pets': 'Dog.owner'},
        'subscriptions')

    name = Field()
    age = Field.int()


class Thing(Model):
    belongs_to('person')
    has_many('features')

    name = Field()
    color = Field()


class Feature(Model):
    belongs_to('thing')
    has_one('price')

    name = Field()


class Price(Model):
    belongs_to('feature')

    value = Field.int()


class Doctor(Model):
    has_many('appointments', {'patients': {'via': 'appointments'}})
    name = Field()


class Patient(Model):
    has_many('appointments', {'doctors': {'via': 'appointments'}})
    name = Field()


class Appointment(Model):
    belongs_to('patient', 'doctor')
    date = Field.datetime()


class User(Model):
    name = Field()
    has_many(
        'memberships', {'organizations': {'via': 'memberships'}},
        {'cover_orgs': {
            'via': 'memberships.organization',
            'where': lambda m: m.is_cover == True}})


class Organization(Model):
    name = Field()
    is_cover = Field.bool(default=False)

    @has_many()
    def admin_memberships3(self):
        return Membership.admins()

    has_many(
        'memberships', {'users': {'via': 'memberships'}},
        {'admin_memberships': {'target': 'Membership', 'scope': 'admins'}},
        {'admins': {'via': 'admin_memberships.user'}},
        {'admin_memberships2': {
            'target': 'Membership', 'where': lambda m: m.role == 'admin'}},
        {'admins2': {'via': 'admin_memberships2.user'}},
        {'admins3': {'via': 'admin_memberships3.user'}})


class Membership(Model):
    belongs_to('user', 'organization')
    role = Field()

    @scope('admins')
    def filter_admins(self):
        return self.role == 'admin'


class House(Model):
    name = Field()


class Mouse(Model):
    tablename = "mice"
    has_many('elephants')
    name = Field()


class NeedSplit(Model):
    name = Field()


class Zoo(Model):
    has_many('animals', 'elephants', {'mice': {'via': 'elephants.mouse'}})
    name = Field()


class Animal(Model):
    belongs_to('zoo')
    name = Field()

    @rowattr('doublename')
    def get_double_name(self, row):
        return row.name * 2

    @rowattr('pretty')
    def get_pretty(self, row):
        return row.name

    @before_insert
    def bi(self, *args, **kwargs):
        pass

    @before_insert
    def bi2(self, *args, **kwargs):
        pass


class Elephant(Animal):
    belongs_to('mouse')
    color = Field()

    @rowattr('pretty')
    def get_pretty(self, row):
        return row.name + " " + row.color

    @before_insert
    def bi2(self, *args, **kwargs):
        pass


class Dog(Model):
    belongs_to({'owner': 'Person'})
    name = Field()


class Subscription(Model):
    belongs_to('person')

    name = Field()
    status = Field.int()
    expires_at = Field.datetime()

    STATUS = {'active': 1, 'suspended': 2, 'other': 3}

    @scope('expired')
    def get_expired(self):
        return self.expires_at < datetime.now()

    @scope('of_status')
    def filter_status(self, *statuses):
        if len(statuses) == 1:
            return self.status == self.STATUS[statuses[0]]
        return self.status.belongs(*[self.STATUS[v] for v in statuses])


@pytest.fixture(scope='module')
def db():
    app = App(__name__)
    db = Database(
        app, config=sdict(
            uri='sqlite://dal.db', auto_connect=True, auto_migrate=True))
    db.define_models([
        Stuff, Person, Thing, Feature, Price, Doctor, Patient, Appointment,
        User, Organization, Membership, House, Mouse, NeedSplit, Zoo, Animal,
        Elephant, Dog, Subscription
    ])
    return db


def test_db_instance(db):
    assert isinstance(db, Database)


def test_table_definition(db):
    assert isinstance(db.Stuff, Table)
    assert isinstance(db[Stuff.tablename], Table)


def test_fields(db):
    assert isinstance(db.Stuff.a, _Field)
    assert db.Stuff.a.type == "string"


def test_validators(db):
    assert len(db.Stuff.a.requires) == 2
    assert isinstance(db.Stuff.a.requires[0], isntEmpty)
    assert isinstance(db.Stuff.a.requires[1], hasLength)


def test_visibility(db):
    assert db.Stuff.a.readable is True
    assert db.Stuff.a.writable is True
    assert db.Stuff.invisible.readable is False
    assert db.Stuff.invisible.writable is False


def test_labels(db):
    assert db.Stuff.a.label == "A label"


def test_comments(db):
    assert db.Stuff.a.comment == "A comment"


def test_updates(db):
    assert db.Stuff.a.update == "a_update"


def test_representation(db):
    assert db.Stuff.a.represent == _represent_f


def test_widgets(db):
    assert db.Stuff.a.widget == _widget_f


# def test_set_helper(db):
#     assert isinstance(db.Stuff.b.requires, notInDb)


def test_computations(db):
    row = sdict(price=12.95, quantity=3)
    rv = db.Stuff.total.compute(row)
    assert rv == 12.95 * 3


def test_callbacks(db):
    fields = ["a", "b", "c"]
    id = 12
    rv = db.Stuff._before_insert[-1](fields)
    assert rv == fields[:-1]
    rv = db.Stuff._after_insert[-1](fields, id)
    assert rv[0] == fields[:-1] and rv[1] == id + 1
    set = {"a": "b"}
    rv = db.Stuff._before_update[-1](set, fields)
    assert rv[0] == set and rv[1] == fields[:-1]
    rv = db.Stuff._after_update[-1](set, fields)
    assert rv[0] == set and rv[1] == fields[:-1]
    rv = db.Stuff._before_delete[-1](set)
    assert rv == set
    rv = db.Stuff._after_delete[-1](set)
    assert rv == set


def test_rowattrs(db):
    db.Stuff._before_insert = []
    db.Stuff._after_insert = []
    db.Stuff.insert(a="foo", b="bar", price=12.95, quantity=3)
    db.commit()
    row = db(db.Stuff).select().first()
    assert row.totalv == 12.95 * 3


def test_rowmethods(db):
    row = db(db.Stuff).select().first()
    assert row.totalm() == 12.95 * 3


def test_modelmethods(db):
    tm = "foo"
    rv = Stuff.method_test(tm)
    assert rv[0] == db and rv[1] == db.Stuff and rv[2] == tm


def test_relations(db):
    p = db.Person.insert(name="Giovanni", age=25)
    t = db.Thing.insert(name="apple", color="red", person=p)
    f = db.Feature.insert(name="tasty", thing=t)
    db.Price.insert(value=5, feature=f)
    p = db.Person(name="Giovanni")
    #: belongs, has_one, has_many
    t = p.things()
    assert len(t) == 1
    assert t[0].name == "apple" and t[0].color == "red" and \
        t[0].person.id == p.id
    f = p.things()[0].features()
    assert len(f) == 1
    assert f[0].name == "tasty" and f[0].thing.id == t[0].id and \
        f[0].thing.person.id == p.id
    m = p.things()[0].features()[0].price()
    assert m.value == 5 and m.feature.id == f[0].id and \
        m.feature.thing.id == t[0].id and m.feature.thing.person.id == p.id
    #: has_many via as shortcut
    assert len(p.features()) == 1
    #: has_many via with join tables logic
    doctor = db.Doctor.insert(name="cox")
    patient = db.Patient.insert(name="mario")
    db.Appointment.insert(doctor=1, patient=1)
    assert len(doctor.patients()) == 1
    assert len(doctor.appointments()) == 1
    assert len(patient.doctors()) == 1
    assert len(patient.appointments()) == 1
    joe = db.User.insert(name='joe')
    jim = db.User.insert(name='jim')
    org = db.Organization.insert(name='')
    org.users.add(joe, role='admin')
    org.users.add(jim, role='manager')
    assert len(org.users()) == 2
    assert len(joe.organizations()) == 1
    assert len(jim.organizations()) == 1
    assert joe.organizations().first().id == org
    assert jim.organizations().first().id == org
    assert joe.memberships().first().role == 'admin'
    assert jim.memberships().first().role == 'manager'
    #: has_many with specified feld
    db.Dog.insert(name='pongo', owner=p)
    assert len(p.pets()) == 1 and p.pets().first().name == 'pongo'
    #: has_many via with specified field
    zoo = db.Zoo.insert(name='magic zoo')
    mouse = db.Mouse.insert(name='jerry')
    db.Elephant.insert(name='dumbo', color='pink', mouse=mouse, zoo=zoo)
    assert len(zoo.mice()) == 1


def test_tablenames(db):
    assert db.House == db.houses
    assert db.Mouse == db.mice
    assert db.NeedSplit == db.need_splits


def test_inheritance(db):
    assert 'name' in db.Animal.fields
    assert 'name' in db.Elephant.fields
    assert 'zoo' in db.Animal.fields
    assert 'zoo' in db.Elephant.fields
    assert 'color' in db.Elephant.fields
    assert 'color' not in db.Animal.fields
    assert Elephant._all_virtuals_['get_double_name'] is \
        Animal._all_virtuals_['get_double_name']
    assert Elephant._all_virtuals_['get_pretty'] is not \
        Animal._all_virtuals_['get_pretty']
    assert Elephant._all_callbacks_['bi'] is \
        Animal._all_callbacks_['bi']
    assert Elephant._all_callbacks_['bi2'] is not \
        Animal._all_callbacks_['bi2']


def test_scopes(db):
    p = db.Person.insert(name="Walter", age=50)
    s = db.Subscription.insert(
        name="a", expires_at=datetime.now() - timedelta(hours=20), person=p,
        status=1)
    s2 = db.Subscription.insert(
        name="b", expires_at=datetime.now() + timedelta(hours=20), person=p,
        status=2)
    db.Subscription.insert(
        name="c", expires_at=datetime.now() + timedelta(hours=20), person=p,
        status=3)
    rows = db(db.Subscription).expired().select()
    assert len(rows) == 1 and rows[0].id == s
    rows = p.subscriptions.expired().select()
    assert len(rows) == 1 and rows[0].id == s
    rows = Subscription.expired().select()
    assert len(rows) == 1 and rows[0].id == s
    rows = db(db.Subscription).of_status('active', 'suspended').select()
    assert len(rows) == 2 and rows[0].id == s and rows[1].id == s2
    rows = p.subscriptions.of_status('active', 'suspended').select()
    assert len(rows) == 2 and rows[0].id == s and rows[1].id == s2
    rows = Subscription.of_status('active', 'suspended').select()
    assert len(rows) == 2 and rows[0].id == s and rows[1].id == s2


def test_relations_scopes(db):
    gus = db.User.insert(name="Gus Fring")
    org = db.Organization.insert(name="Los pollos hermanos")
    org.users.add(gus, role="admin")
    frank = db.User.insert(name="Frank")
    org.users.add(frank, role='manager')
    assert org.admins.count() == 1
    assert org.admins2.count() == 1
    assert org.admins3.count() == 1
    org2 = db.Organization.insert(name="Laundry", is_cover=True)
    org2.users.add(gus, role="admin")
    assert len(gus.cover_orgs()) == 1
    assert gus.cover_orgs().first().id == org2
    org.delete_record()
    org2.delete_record()
    #: creation/addition
    org = db.Organization.insert(name="Los pollos hermanos")
    org.admins.add(gus)
    assert org.admins.count() == 1
    org.delete_record()
    org = db.Organization.insert(name="Los pollos hermanos")
    org.admins2.add(gus)
    assert org.admins2.count() == 1
    org.delete_record()
    org = db.Organization.insert(name="Los pollos hermanos")
    org.admins3.add(gus)
    assert org.admins3.count() == 1
    org.delete_record()
    gus = User.get(name="Gus Fring")
    org2 = db.Organization.insert(name="Laundry", is_cover=True)
    gus.cover_orgs.add(org2)
    assert len(gus.cover_orgs()) == 1
    assert gus.cover_orgs().first().id == org2


def test_model_where(db):
    assert Subscription.where(lambda s: s.status == 1).query == \
        db(db.Subscription.status == 1).query
