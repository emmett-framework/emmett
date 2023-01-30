# -*- coding: utf-8 -*-
"""
    tests.orm
    ---------

    Test pyDAL implementation over Emmett.
"""

import pytest

from datetime import datetime, timedelta
from uuid import uuid4

from pydal.objects import Table
from pydal import Field as _Field
from emmett import App, sdict, now
from emmett.orm import (
    Database, Field, Model,
    compute,
    before_insert, after_insert,
    before_update, after_update,
    before_delete, after_delete,
    before_save, after_save,
    before_destroy, after_destroy,
    before_commit, after_commit,
    rowattr, rowmethod,
    has_one, has_many, belongs_to, refers_to,
    scope
)
from emmett.orm.migrations.utils import generate_runtime_migration
from emmett.orm.objects import TransactionOps
from emmett.orm.errors import MissingFieldsForCompute
from emmett.validators import isntEmpty, hasLength


CALLBACK_OPS = {
    "before_insert": [],
    "before_update": [],
    "before_delete": [],
    "before_save":[],
    "before_destroy": [],
    "after_insert": [],
    "after_update": [],
    "after_delete": [],
    "after_save":[],
    "after_destroy": []
}
COMMIT_CALLBACKS = {
    "all": [],
    "insert": [],
    "update": [],
    "delete": [],
    "save": [],
    "destroy": []
}


def _represent_f(value):
    return value


def _widget_f(field, value):
    return value


class Stuff(Model):
    a = Field.string()
    b = Field()
    price = Field.float()
    quantity = Field.int()
    total = Field.float()
    total_watch = Field.float()
    invisible = Field()

    validation = {
        "a": {'presence': True},
        "total": {"allow": "empty"},
        "total_watch": {"allow": "empty"}
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

    @compute('total')
    def eval_total(self, row):
        return row.price * row.quantity

    @compute('total_watch', watch=['price', 'quantity'])
    def eval_total_watch(self, row):
        return row.price * row.quantity

    @before_insert
    def bi(self, fields):
        CALLBACK_OPS['before_insert'].append(fields)

    @after_insert
    def ai(self, fields, id):
        CALLBACK_OPS['after_insert'].append((fields, id))

    @before_update
    def bu(self, set, fields):
        CALLBACK_OPS['before_update'].append((set, fields))

    @after_update
    def au(self, set, fields):
        CALLBACK_OPS['after_update'].append((set, fields))

    @before_delete
    def bd(self, set):
        CALLBACK_OPS['before_delete'].append(set)

    @after_delete
    def ad(self, set):
        CALLBACK_OPS['after_delete'].append(set)

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


class Product(Model):
    name = Field.string()
    price = Field.float(default=0.0)


class Cart(Model):
    has_many({"elements": "CartElement"})

    updated_at = Field.datetime(default=now, update=now)
    total_denorm = Field.float(default=0.0)
    revision = Field.string(default=lambda: uuid4().hex, update=lambda: uuid4().hex)

    def _sum_elements(self, row):
        summable = (CartElement.quantity.cast("float") * Product.price).sum()
        sum = row.elements.join("product").select(summable).first()
        return sum[summable] or 0.0

    @before_save
    def _rebuild_total(self, row):
        row.total_denorm = self._sum_elements(row)

    @rowattr("total")
    def _compute_total(self, row):
        return self._sum_elements(row)


class CartElement(Model):
    belongs_to("product", "cart")

    updated_at = Field.datetime(default=now, update=now)
    quantity = Field.int(default=1)
    price_denorm = Field.float(default=0.0)

    @before_save
    def _rebuild_price(self, row):
        row.price_denorm = row.quantity * row.product.price

    @after_save
    def _refresh_cart_after_update(self, row):
        row.cart.save()

    @before_destroy
    def _undo_quantity_on_removal(self, row):
        row.quantity = 0
        row.price_denorm = 0

    @after_destroy
    def _refresh_cart_after_removal(self, row):
        row.cart.save()

    @rowattr("price")
    def _compute_price(self, row):
        return row.quantity * row.product.price


class SelfRef(Model):
    refers_to({'parent': 'self'})

    name = Field.string()


class CustomPKType(Model):
    id = Field.string()


class CustomPKName(Model):
    primary_keys = ["name"]
    name = Field.string()


class CustomPKMulti(Model):
    primary_keys = ["first_name", "last_name"]
    first_name = Field.string()
    last_name = Field.string()


class CommitWatcher(Model):
    foo = Field.string()
    created_at = Field.datetime(default=now)
    updated_at = Field.datetime(default=now, update=now)

    @before_commit
    def _commit_watch_before(self, op_type, ctx):
        COMMIT_CALLBACKS["all"].append(("before", op_type, ctx))

    @after_commit
    def _commit_watch_after(self, op_type, ctx):
        COMMIT_CALLBACKS["all"].append(("after", op_type, ctx))

    @before_commit.operation(TransactionOps.save)
    def _commit_watch_before_save(self, ctx):
        COMMIT_CALLBACKS["save"].append(("before", ctx))

    @after_commit.operation(TransactionOps.save)
    def _commit_watch_after_save(self, ctx):
        COMMIT_CALLBACKS["save"].append(("after", ctx))

    @before_commit.operation(TransactionOps.destroy)
    def _commit_watch_before_destroy(self, ctx):
        COMMIT_CALLBACKS["destroy"].append(("before", ctx))

    @after_commit.operation(TransactionOps.destroy)
    def _commit_watch_after_destroy(self, ctx):
        COMMIT_CALLBACKS["destroy"].append(("after", ctx))


@pytest.fixture(scope='module')
def _db():
    app = App(__name__)
    db = Database(
        app, config=sdict(
            uri=f'sqlite://{uuid4().hex}.db',
            auto_connect=True
        )
    )
    db.define_models(
        Stuff, Person, Thing, Feature, Price, Dog, Subscription,
        Doctor, Patient, Appointment,
        User, Organization, Membership,
        House, Mouse, NeedSplit, Zoo, Animal, Elephant,
        Product, Cart, CartElement,
        SelfRef,
        CustomPKType, CustomPKName, CustomPKMulti,
        CommitWatcher
    )
    return db


@pytest.fixture(scope='function')
def db(_db):
    migration = generate_runtime_migration(_db)
    migration.up()
    yield _db
    migration.down()


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
    #: no watch
    row = sdict(price=12.95, quantity=3)
    rv = db.Stuff.total.compute(row)
    assert rv == 12.95 * 3
    #: watch fulfill
    row = sdict(price=12.95, quantity=3)
    rv = db.Stuff.total_watch.compute(row)
    assert rv == 12.95 * 3
    #: watch missing field
    row = sdict(price=12.95)
    with pytest.raises(MissingFieldsForCompute):
        db.Stuff.total_watch.compute(row)
    #: update flow
    res = Stuff.create(a="foo", price=12.95, quantity=1)
    row = Stuff.get(res.id)
    with pytest.raises(MissingFieldsForCompute):
        row.update_record(quantity=2)
    row.update_record(price=row.price, quantity=2)
    assert row.total == row.price * 2
    assert row.total_watch == row.price * 2


def test_callbacks(db):
    fields = {"a": 1, "b": 2, "c": 3}
    id = 12
    db.Stuff._before_insert[-1](fields)
    assert CALLBACK_OPS["before_insert"][-1] == fields
    db.Stuff._after_insert[-1](fields, id)
    res = CALLBACK_OPS["after_insert"][-1]
    assert res[0] == fields and res[1] == id
    set = {"a": "b"}
    db.Stuff._before_update[-1](set, fields)
    res = CALLBACK_OPS["before_update"][-1]
    assert res[0] == set and res[1] == fields
    db.Stuff._after_update[-1](set, fields)
    res = CALLBACK_OPS["after_update"][-1]
    assert res[0] == set and res[1] == fields
    db.Stuff._before_delete[-1](set)
    res = CALLBACK_OPS["before_delete"][-1]
    assert res == set
    db.Stuff._after_delete[-1](set)
    res = CALLBACK_OPS["after_delete"][-1]
    assert res == set


def test_save(db):
    p1 = db.Product.insert(name="foo", price=2.99)
    p2 = db.Product.insert(name="bar", price=7.49)
    cart = db.Cart.insert()
    assert cart.total == 0
    assert cart.total_denorm == 0

    cart_rev = cart.revision
    item = CartElement.new(cart=cart, product=p1)
    item.save()
    assert item.price == p1.price
    assert item.price_denorm == p1.price
    cart = Cart.get(cart.id)
    assert cart.total == p1.price
    assert cart.total_denorm == p1.price
    assert cart.revision != cart_rev

    cart_rev = cart.revision
    item = CartElement.new(cart=cart, product=p2, quantity=3)
    item.save()
    assert item.price == p2.price * 3
    assert item.price_denorm == p2.price * 3
    cart = Cart.get(cart.id)
    assert cart.total == p1.price + p2.price * 3
    assert cart.total_denorm == p1.price + p2.price * 3
    assert cart.revision != cart_rev


def test_destroy(db):
    p1 = db.Product.insert(name="foo", price=2.99)
    p2 = db.Product.insert(name="bar", price=7.49)
    cart = db.Cart.insert()

    item = CartElement.new(cart=cart, product=p1)
    item.save()
    item = CartElement.new(cart=cart, product=p2, quantity=3)
    item.save()

    cart = Cart.get(cart.id)
    cart_rev = cart.revision

    item.destroy()
    assert not item.id
    assert not item.price
    assert not item.price_denorm
    cart = Cart.get(cart.id)
    assert cart.total == p1.price
    assert cart.total_denorm == p1.price
    assert cart.revision != cart_rev


def test_commit_callbacks(db):
    #: insert
    row = db.CommitWatcher.insert(foo="test1")
    assert not COMMIT_CALLBACKS["all"]
    db.commit()

    assert len(COMMIT_CALLBACKS["all"]) == 2

    before, after = COMMIT_CALLBACKS["all"]

    order, op_type, ctx = before
    assert order == "before"
    assert op_type == TransactionOps.insert
    assert ctx.values.foo == "test1"
    assert ctx.return_value == row.id

    order, op_type, ctx = after
    assert order == "after"
    assert op_type == TransactionOps.insert
    assert ctx.values.foo == "test1"
    assert ctx.return_value == row.id

    COMMIT_CALLBACKS["all"].clear()

    #: update
    row.update_record(foo="test1a")
    assert not COMMIT_CALLBACKS["all"]
    db.commit()

    assert len(COMMIT_CALLBACKS["all"]) == 2

    before, after = COMMIT_CALLBACKS["all"]

    order, op_type, ctx = before
    assert order == "before"
    assert op_type == TransactionOps.update
    assert ctx.dbset
    assert ctx.values.foo == "test1a"
    assert ctx.return_value == 1

    order, op_type, ctx = after
    assert order == "after"
    assert op_type == TransactionOps.update
    assert ctx.dbset
    assert ctx.values.foo == "test1a"
    assert ctx.return_value == 1

    COMMIT_CALLBACKS["all"].clear()

    #: delete
    row.delete_record()
    assert not COMMIT_CALLBACKS["all"]
    db.commit()

    assert len(COMMIT_CALLBACKS["all"]) == 2

    before, after = COMMIT_CALLBACKS["all"]

    order, op_type, ctx = before
    assert order == "before"
    assert op_type == TransactionOps.delete
    assert ctx.dbset
    assert ctx.return_value == 1

    order, op_type, ctx = after
    assert order == "after"
    assert op_type == TransactionOps.delete
    assert ctx.dbset
    assert ctx.return_value == 1

    COMMIT_CALLBACKS["all"].clear()

    #: save:insert
    row = CommitWatcher.new(foo="test2")
    row.save()
    assert not COMMIT_CALLBACKS["all"]
    assert not COMMIT_CALLBACKS["save"]
    db.commit()

    assert len(COMMIT_CALLBACKS["all"]) == 4
    assert len(COMMIT_CALLBACKS["save"]) == 2

    before_ins, before_save, after_ins, after_save = COMMIT_CALLBACKS["all"]

    order, op_type, ctx = before_ins
    assert order == "before"
    assert op_type == TransactionOps.insert
    assert ctx.values.foo == "test2"
    assert ctx.return_value == row.id

    order, op_type, ctx = after_ins
    assert order == "after"
    assert op_type == TransactionOps.insert
    assert ctx.values.foo == "test2"
    assert ctx.return_value == row.id

    order, op_type, ctx = before_save
    assert order == "before"
    assert op_type == TransactionOps.save
    assert ctx.values.foo == "test2"
    assert ctx.return_value == row.id
    assert ctx.row.id == row.id
    assert "id" in ctx.changes

    order, op_type, ctx = after_save
    assert order == "after"
    assert op_type == TransactionOps.save
    assert ctx.values.foo == "test2"
    assert ctx.return_value == row.id
    assert ctx.row.id == row.id
    assert "id" in ctx.changes

    before_save, after_save = COMMIT_CALLBACKS["save"]

    order, ctx = before_save
    assert order == "before"
    assert ctx.values.foo == "test2"
    assert ctx.return_value == row.id
    assert ctx.row.id == row.id
    assert "id" in ctx.changes

    order, ctx = after_save
    assert order == "after"
    assert ctx.values.foo == "test2"
    assert ctx.return_value == row.id
    assert ctx.row.id == row.id
    assert "id" in ctx.changes

    COMMIT_CALLBACKS["all"].clear()
    COMMIT_CALLBACKS["save"].clear()

    #: save:update
    row.foo = "test2a"
    row.save()
    assert not COMMIT_CALLBACKS["all"]
    assert not COMMIT_CALLBACKS["save"]
    db.commit()

    assert len(COMMIT_CALLBACKS["all"]) == 4
    assert len(COMMIT_CALLBACKS["save"]) == 2

    before_upd, before_save, after_upd, after_save = COMMIT_CALLBACKS["all"]

    order, op_type, ctx = before_upd
    assert order == "before"
    assert op_type == TransactionOps.update
    assert ctx.dbset
    assert ctx.values.foo == "test2a"
    assert ctx.return_value == 1

    order, op_type, ctx = after_upd
    assert order == "after"
    assert op_type == TransactionOps.update
    assert ctx.dbset
    assert ctx.values.foo == "test2a"
    assert ctx.return_value == 1

    order, op_type, ctx = before_save
    assert order == "before"
    assert op_type == TransactionOps.save
    assert ctx.dbset
    assert ctx.values.foo == "test2a"
    assert ctx.return_value == 1
    assert ctx.row.id == row.id
    assert set(ctx.changes.keys()).issubset({"foo", "updated_at"})

    order, op_type, ctx = after_save
    assert order == "after"
    assert op_type == TransactionOps.save
    assert ctx.dbset
    assert ctx.values.foo == "test2a"
    assert ctx.return_value == 1
    assert ctx.row.id == row.id
    assert set(ctx.changes.keys()).issubset({"foo", "updated_at"})

    before_save, after_save = COMMIT_CALLBACKS["save"]

    order, ctx = before_save
    assert order == "before"
    assert ctx.dbset
    assert ctx.values.foo == "test2a"
    assert ctx.return_value == 1
    assert ctx.row.id == row.id
    assert set(ctx.changes.keys()).issubset({"foo", "updated_at"})

    order, ctx = after_save
    assert order == "after"
    assert ctx.dbset
    assert ctx.values.foo == "test2a"
    assert ctx.return_value == 1
    assert ctx.row.id == row.id
    assert set(ctx.changes.keys()).issubset({"foo", "updated_at"})

    COMMIT_CALLBACKS["all"].clear()
    COMMIT_CALLBACKS["save"].clear()

    #: destroy
    row.destroy()
    assert not COMMIT_CALLBACKS["all"]
    assert not COMMIT_CALLBACKS["destroy"]
    db.commit()

    assert len(COMMIT_CALLBACKS["all"]) == 4
    assert len(COMMIT_CALLBACKS["destroy"]) == 2

    before_del, before_destroy, after_del, after_destroy = COMMIT_CALLBACKS["all"]

    order, op_type, ctx = before_del
    assert order == "before"
    assert op_type == TransactionOps.delete
    assert ctx.dbset
    assert ctx.return_value == 1

    order, op_type, ctx = after_del
    assert order == "after"
    assert op_type == TransactionOps.delete
    assert ctx.dbset
    assert ctx.return_value == 1

    order, op_type, ctx = before_destroy
    assert order == "before"
    assert op_type == TransactionOps.destroy
    assert ctx.dbset
    assert ctx.return_value == 1
    assert ctx.row.id == row.id

    order, op_type, ctx = after_destroy
    assert order == "after"
    assert op_type == TransactionOps.destroy
    assert ctx.dbset
    assert ctx.return_value == 1
    assert ctx.row.id == row.id

    before_destroy, after_destroy = COMMIT_CALLBACKS["destroy"]

    order, ctx = before_destroy
    assert order == "before"
    assert ctx.dbset
    assert ctx.return_value == 1
    assert ctx.row.id == row.id

    order, ctx = after_destroy
    assert order == "after"
    assert ctx.dbset
    assert ctx.return_value == 1
    assert ctx.row.id == row.id

    COMMIT_CALLBACKS["all"].clear()
    COMMIT_CALLBACKS["destroy"].clear()


def test_callbacks_skip(db):
    for stack in CALLBACK_OPS.values():
        stack.clear()
    for stack in COMMIT_CALLBACKS.values():
        stack.clear()

    #: insert
    row = db.CommitWatcher.insert(foo="test1", skip_callbacks=True)
    db.commit()
    assert not CALLBACK_OPS["before_insert"]
    assert not CALLBACK_OPS["after_insert"]
    assert not COMMIT_CALLBACKS["all"]
    assert not COMMIT_CALLBACKS["insert"]

    #: update
    row.update_record(foo="test1a", skip_callbacks=True)
    db.commit()
    assert not CALLBACK_OPS["before_update"]
    assert not CALLBACK_OPS["after_update"]
    assert not COMMIT_CALLBACKS["all"]
    assert not COMMIT_CALLBACKS["update"]

    #: delete
    row.delete_record(skip_callbacks=True)
    db.commit()
    assert not CALLBACK_OPS["before_delete"]
    assert not CALLBACK_OPS["after_delete"]
    assert not COMMIT_CALLBACKS["all"]
    assert not COMMIT_CALLBACKS["delete"]

    #: save:insert
    row = CommitWatcher.new(foo="test2")
    row.save(skip_callbacks=True)
    db.commit()
    assert not CALLBACK_OPS["before_save"]
    assert not CALLBACK_OPS["after_save"]
    assert not CALLBACK_OPS["before_insert"]
    assert not CALLBACK_OPS["after_insert"]
    assert not COMMIT_CALLBACKS["all"]
    assert not COMMIT_CALLBACKS["save"]
    assert not COMMIT_CALLBACKS["insert"]

    #: save:update
    row.foo = "test2a"
    row.save(skip_callbacks=True)
    db.commit()
    assert not CALLBACK_OPS["before_save"]
    assert not CALLBACK_OPS["after_save"]
    assert not CALLBACK_OPS["before_update"]
    assert not CALLBACK_OPS["after_update"]
    assert not COMMIT_CALLBACKS["all"]
    assert not COMMIT_CALLBACKS["save"]
    assert not COMMIT_CALLBACKS["update"]

    #: destroy
    row.destroy(skip_callbacks=True)
    db.commit()
    assert not CALLBACK_OPS["before_destroy"]
    assert not CALLBACK_OPS["after_destroy"]
    assert not CALLBACK_OPS["before_delete"]
    assert not CALLBACK_OPS["after_delete"]
    assert not COMMIT_CALLBACKS["all"]
    assert not COMMIT_CALLBACKS["destroy"]
    assert not COMMIT_CALLBACKS["delete"]


def test_rowattrs(db):
    db.Stuff._before_insert = []
    db.Stuff._after_insert = []
    res = db.Stuff.insert(a="foo", b="bar", price=12.95, quantity=3)
    db.commit()
    row = Stuff.get(res)
    assert row.totalv == 12.95 * 3


def test_rowmethods(db):
    db.Stuff._before_insert = []
    db.Stuff._after_insert = []
    res = db.Stuff.insert(a="foo", b="bar", price=12.95, quantity=3)
    db.commit()
    row = Stuff.get(res)
    assert row.totalm() == 12.95 * 3


def test_modelmethods(db):
    tm = "foo"
    rv = Stuff.method_test(tm)
    assert rv[0] == db and rv[1] == db.Stuff and rv[2] == tm


def test_relations(db):
    p1 = db.Person.insert(name="Giovanni", age=25)
    p2 = db.Person.insert(name="Giorgio", age=30)
    t1 = db.Thing.insert(name="apple", color="red", person=p1)
    t2 = db.Thing.insert(name="apple", color="green", person=p1)
    f = db.Feature.insert(name="tasty", thing=t1)
    db.Price.insert(value=5, feature=f)
    #: belongs, has_one, has_many
    p1 = db.Person(name="Giovanni")
    p2 = db.Person(name="Giorgio")
    assert p1.things.count() == 2
    assert p2.things.count() == 0
    t = p1.things.where(lambda t: t.color == "red").select()
    assert len(t) == 1
    assert t[0].name == "apple" and t[0].color == "red" and t[0].person.id == p1.id
    f = p1.things()[0].features()
    assert len(f) == 1
    assert f[0].name == "tasty" and f[0].thing.id == t[0].id and \
        f[0].thing.person.id == p1.id
    m = p1.things()[0].features()[0].price()
    assert (
        m.value == 5 and m.feature.id == f[0].id and
        m.feature.thing.id == t[0].id and m.feature.thing.person.id == p1.id
    )
    p2.things.add(t2)
    assert p1.things.count() == 1
    assert p2.things.count() == 1
    t = p2.things()
    assert len(t) == 1
    assert t[0].name == "apple" and t[0].color == "green" and t[0].person.id == p2.id
    p2.things.remove(t2)
    assert p2.things.count() == 0
    assert db(db.things).count() == 1
    #: has_many via as shortcut
    assert len(p1.features()) == 1
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
    org.users.remove(joe)
    org.users.remove(jim)
    assert len(org.users(reload=True)) == 0
    assert len(joe.organizations(reload=True)) == 0
    assert len(jim.organizations(reload=True)) == 0
    #: has_many with specified feld
    db.Dog.insert(name='pongo', owner=p1)
    assert len(p1.pets()) == 1 and p1.pets().first().name == 'pongo'
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
    org.users.remove(gus)
    org.users.remove(frank)
    assert org.admins.count() == 0
    assert org.admins2.count() == 0
    assert org.admins3.count() == 0
    org2 = db.Organization.insert(name="Laundry", is_cover=True)
    org2.users.add(gus, role="admin")
    assert gus.cover_orgs.count() == 1
    assert gus.cover_orgs().first().id == org2
    org2.users.remove(gus)
    assert gus.cover_orgs.count() == 0
    org.delete_record()
    org2.delete_record()
    #: creation/addition
    org = db.Organization.insert(name="Los pollos hermanos")
    org.admins.add(gus)
    assert org.admins.count() == 1
    org.admins.remove(gus)
    assert org.admins.count() == 0
    org.delete_record()
    org = db.Organization.insert(name="Los pollos hermanos")
    org.admins2.add(gus)
    assert org.admins2.count() == 1
    org.admins2.remove(gus)
    assert org.admins2.count() == 0
    org.delete_record()
    org = db.Organization.insert(name="Los pollos hermanos")
    org.admins3.add(gus)
    assert org.admins3.count() == 1
    org.admins3.remove(gus)
    assert org.admins3.count() == 0
    org.delete_record()
    gus = User.get(name="Gus Fring")
    org2 = db.Organization.insert(name="Laundry", is_cover=True)
    gus.cover_orgs.add(org2)
    assert gus.cover_orgs.count() == 1
    assert gus.cover_orgs().first().id == org2
    gus.cover_orgs.remove(org2)
    assert gus.cover_orgs.count() == 0


def test_model_where(db):
    assert Subscription.where(lambda s: s.status == 1).query == \
        db(db.Subscription.status == 1).query


def test_model_first(db):
    p = db.Person.insert(name="Walter", age=50)
    db.Subscription.insert(
        name="a",
        expires_at=datetime.now() + timedelta(hours=20),
        person=p,
        status=1
    )
    db.Subscription.insert(
        name="b",
        expires_at=datetime.now() + timedelta(hours=20),
        person=p,
        status=1
    )
    db.CustomPKType.insert(id="a")
    db.CustomPKType.insert(id="b")
    db.CustomPKName.insert(name="a")
    db.CustomPKName.insert(name="b")
    db.CustomPKMulti.insert(first_name="foo", last_name="bar")
    db.CustomPKMulti.insert(first_name="foo", last_name="baz")
    db.CustomPKMulti.insert(first_name="bar", last_name="baz")

    assert Subscription.first().id == Subscription.all().select(
        orderby=Subscription.id,
        limitby=(0, 1)
    ).first().id
    assert CustomPKType.first().id == CustomPKType.all().select(
        orderby=CustomPKType.id,
        limitby=(0, 1)
    ).first().id
    assert CustomPKName.first().name == CustomPKName.all().select(
        orderby=CustomPKName.name,
        limitby=(0, 1)
    ).first().name
    assert CustomPKMulti.first() == CustomPKMulti.all().select(
        orderby=CustomPKMulti.first_name|CustomPKMulti.last_name,
        limitby=(0, 1)
    ).first()


def test_model_last(db):
    p = db.Person.insert(name="Walter", age=50)
    db.Subscription.insert(
        name="a",
        expires_at=datetime.now() + timedelta(hours=20),
        person=p,
        status=1
    )
    db.Subscription.insert(
        name="b",
        expires_at=datetime.now() + timedelta(hours=20),
        person=p,
        status=1
    )
    db.CustomPKType.insert(id="a")
    db.CustomPKType.insert(id="b")
    db.CustomPKName.insert(name="a")
    db.CustomPKName.insert(name="b")
    db.CustomPKMulti.insert(first_name="foo", last_name="bar")
    db.CustomPKMulti.insert(first_name="foo", last_name="baz")
    db.CustomPKMulti.insert(first_name="bar", last_name="baz")

    assert Subscription.last().id == Subscription.all().select(
        orderby=~Subscription.id,
        limitby=(0, 1)
    ).first().id
    assert CustomPKType.last().id == CustomPKType.all().select(
        orderby=~CustomPKType.id,
        limitby=(0, 1)
    ).first().id
    assert CustomPKName.last().name == CustomPKName.all().select(
        orderby=~CustomPKName.name,
        limitby=(0, 1)
    ).first().name
    assert CustomPKMulti.last() == CustomPKMulti.all().select(
        orderby=~CustomPKMulti.first_name|~CustomPKMulti.last_name,
        limitby=(0, 1)
    ).first()
