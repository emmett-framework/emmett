# -*- coding: utf-8 -*-
"""
    tests.orm_row
    -------------

    Test ORM row objects
"""

import pickle
import pytest

from uuid import uuid4

from emmett import App, sdict, now
from emmett.orm import (
    Database, Model, Field, belongs_to, has_many, refers_to, rowattr, rowmethod
)
from emmett.orm.errors import ValidationError
from emmett.orm.helpers import RowReferenceMixin
from emmett.orm.migrations.utils import generate_runtime_migration
from emmett.orm.objects import Row


class One(Model):
    has_many("twos", "threes")

    foo = Field.string(notnull=True)
    bar = Field.string()

    @rowattr("twos_list")
    def _row_attr_test(self, row):
        return [el.foo for el in row.twos()]


class Two(Model):
    belongs_to("one")

    foo = Field.string()
    bar = Field.string()


class Three(Model):
    refers_to("one")

    foo = Field.string()


class Override(Model):
    foo = Field.string()
    deleted_at = Field.datetime()

    validation = {"deleted_at": {"allow": "empty"}}

    @rowattr("test")
    def _row_attr_test(self, row):
        return "test"

    @rowmethod("destroy")
    def _row_destroy(self, row):
        row.deleted_at = now()
        row.save()

    @rowmethod("force_destroy")
    def _row_force_destroy(self, row):
        self.super_rowmethod("destroy")(row)


class Crypted(Model):
    foo = Field.string()
    bar = Field.password()


@pytest.fixture(scope='module')
def _db():
    app = App(__name__)
    db = Database(
        app,
        config=sdict(
            uri=f'sqlite://{uuid4().hex}.db',
            auto_connect=True
        )
    )
    db.define_models(One, Two, Three, Override, Crypted)
    return db

@pytest.fixture(scope='function')
def db(_db):
    migration = generate_runtime_migration(_db)
    migration.up()
    yield _db
    migration.down()


def test_rowclass(db):
    ret = db.One.insert(foo="test1", bar="test2")
    db.Two.insert(one=ret, foo="test1", bar="test2")

    ret._allocate_()
    assert type(ret._refrecord) == One._instance_()._rowclass_

    row = One.get(ret.id)
    assert type(row) == One._instance_()._rowclass_

    row = One.first()
    assert type(row) == One._instance_()._rowclass_

    row = db(db.One).select().first()
    assert type(row) == One._instance_()._rowclass_

    row = db(db.One).select(db.One.ALL).first()
    assert type(row) == One._instance_()._rowclass_

    row = One.all().select().first()
    assert type(row) == One._instance_()._rowclass_

    row = One.where(lambda m: m.id != None).select().first()
    assert type(row) == One._instance_()._rowclass_

    row = db(db.One).select().first()
    assert type(row) == One._instance_()._rowclass_

    row = db(db.One).select(db.One.ALL).first()
    assert type(row) == One._instance_()._rowclass_

    row = One.all().select(One.bar).first()
    assert type(row) == Row

    row = db(db.One).select(One.bar).first()
    assert type(row) == Row

    row = One.all().join("twos").select().first()
    assert type(row) == One._instance_()._rowclass_
    assert type(row.twos().first()) == Two._instance_()._rowclass_

    row = One.all().join("twos").select(One.table.ALL, Two.table.ALL).first()
    assert type(row) == One._instance_()._rowclass_
    assert type(row.twos().first()) == Two._instance_()._rowclass_

    row = One.all().join("twos").select(One.foo, Two.foo).first()
    assert type(row) == Row
    assert type(row.ones) == Row
    assert type(row.twos) == Row

    row = db(Two.one == One.id).select().first()
    assert type(row) == Row
    assert type(row.ones) == One._instance_()._rowclass_
    assert type(row.twos) == Two._instance_()._rowclass_

    row = db(Two.one == One.id).select(One.table.ALL, Two.foo).first()
    assert type(row) == Row
    assert type(row.ones) == One._instance_()._rowclass_
    assert type(row.twos) == Row

    row = db(Two.one == One.id).select(One.foo, Two.foo).first()
    assert type(row) == Row
    assert type(row.ones) == Row
    assert type(row.twos) == Row

    for row in db(Two.one == One.id).iterselect():
        assert type(row) == Row
        assert type(row.ones) == One._instance_()._rowclass_
        assert type(row.twos) == Two._instance_()._rowclass_

    for row in db(Two.one == One.id).iterselect(One.table.ALL, Two.foo):
        assert type(row) == Row
        assert type(row.ones) == One._instance_()._rowclass_
        assert type(row.twos) == Row

    for row in db(Two.one == One.id).iterselect(One.foo, Two.foo):
        assert type(row) == Row
        assert type(row.ones) == Row
        assert type(row.twos) == Row


def test_concrete(db):
    row = One.new(foo="test")
    assert not row._concrete

    row.save()
    assert row._concrete

    row = One.get(row.id)
    assert row._concrete


def test_changes(db):
    row = One.new(foo="test1")
    assert not row.has_changed

    row.bar = "test2"
    assert row.has_changed
    assert row.has_changed_value("bar")
    assert row.get_value_change("bar") == (None, "test2")

    row.bar = "test2a"
    assert row.has_changed
    assert row.has_changed_value("bar")
    assert row.get_value_change("bar") == (None, "test2a")

    row.bar = None
    assert not row.has_changed
    assert not row.has_changed_value("bar")
    assert row.get_value_change("bar") is None

    row.update(bar="test2b")
    assert row.has_changed
    assert row.has_changed_value("bar")
    assert row.get_value_change("bar") == (None, "test2b")

    row.update({"bar": "test2c"})
    assert row.has_changed
    assert row.has_changed_value("bar")
    assert row.get_value_change("bar") == (None, "test2c")

    row.update(bar=None)
    assert not row.has_changed
    assert not row.has_changed_value("bar")
    assert row.get_value_change("bar") is None

    row.bar = "test2"
    row.save()
    assert not row.has_changed


def test_validation_methods(db):
    row = One.new()
    assert not row.is_valid
    assert set(row.validation_errors.keys()).issubset({"foo"})
    assert not row.save()
    with pytest.raises(ValidationError):
        row.save(raise_on_error=True)

    row.foo = "test"
    assert row.is_valid
    assert not row.validation_errors
    assert row.save()


def test_clone_methods(db):
    row = One.new(foo="test1")
    row.bar = "test2"

    row2 = row.clone()
    row3 = row.clone_changed()

    assert not row2._concrete
    assert not row2.has_changed
    assert not row2.bar
    assert not row3._concrete
    assert not row3.has_changed
    assert row3.bar == "test2"

    row.save()
    row.foo = "test1a"
    row2 = row.clone()
    row3 = row.clone_changed()

    assert row2._concrete
    assert not row2.has_changed
    assert row2.foo == "test1"
    assert row3._concrete
    assert not row3.has_changed
    assert row3.foo == "test1a"


def test_refresh(db):
    row = One.new(foo="test1")
    assert not row.refresh()

    row.save()
    assert row.refresh()

    row.foo = "test2"
    assert row.refresh()
    assert row.foo == "test1"


def test_methods_override(db):
    row = Override.new(foo="test")
    row.save()
    assert row.id
    assert not row.deleted_at

    row.destroy()
    assert row.id
    assert row.deleted_at

    row.force_destroy()
    assert not row.id


def test_attributes(db):
    row = One.new(foo="test", baz="test")
    assert row._fields == {"id": None, "foo": "test", "bar": None}
    assert row.__dict__ == {"baz": "test"}

    assert row.get("foo") == "test"
    assert row.get("baz") == "test"
    assert row.get("test", "foobar") == "foobar"

    assert "foo" in row
    assert "baz" in row
    assert "test" not in row

    row.save()
    assert row.__dict__ == {"baz": "test"}

    row.foo = "test1"
    row.baz = "test1"
    assert set(row._changes.keys()) == {"foo", "baz"}

    row.save()
    assert set(row._changes.keys()) == {"baz"}

    row.refresh()
    assert not row.__dict__
    assert not row._changes


def test_relation_wrappers(db):
    r1 = db.One.insert(foo="test1")
    r2 = db.One.insert(foo="test2")

    r = Two.new()
    assert not r.one

    r = Two.new(one=None)
    assert not r.one

    r = Two.new(one=r1)
    assert isinstance(r.one, RowReferenceMixin)

    r = Two.new(one=r1.id)
    assert isinstance(r.one, RowReferenceMixin)

    r = Two.new(one=One.get(r1))
    assert isinstance(r.one, RowReferenceMixin)

    r.one = r2.id
    assert isinstance(r.one, RowReferenceMixin)

    r = Three.new()
    assert not r.one

    r = Three.new(one=None)
    assert not r.one

    r = Three.new(one=r1)
    assert isinstance(r.one, RowReferenceMixin)

    r = Three.new(one=r1.id)
    assert isinstance(r.one, RowReferenceMixin)

    r = Three.new(one=One.get(r1))
    assert isinstance(r.one, RowReferenceMixin)

    r.one = r2.id
    assert isinstance(r.one, RowReferenceMixin)


def test_password_wrapper(db):
    db.Crypted.validate_and_insert(foo="foobar", bar="foobar")

    row = Crypted.first()
    crypted_value = str(row.bar)

    row.save()
    assert str(row.bar) == crypted_value

    row.foo = "test"
    row.save()
    assert str(row.bar) == crypted_value

    row.bar = "testtest"
    row.save()
    assert str(row.bar) != crypted_value


def test_pickle(db):
    r1 = One.new(foo="test")
    r1.save()
    r2 = Two.new(one=r1, foo="test")
    r2.save()
    r3 = Override.new(foo="test")
    r3.save()

    assert r1.twos_list == ["test"]
    assert r2.one.foo == "test"
    assert r3.test == "test"

    r1.inject = "test"
    r2.inject = "test"
    r3.inject = "test"

    d1 = pickle.dumps(r1)
    l1 = pickle.loads(d1)

    assert l1._fields == r1._fields
    assert l1.__dict__ == r1.__dict__

    d2 = pickle.dumps(r2)
    l2 = pickle.loads(d2)

    assert l2._fields == r2._fields
    assert l2.__dict__ == r2.__dict__

    d3 = pickle.dumps(r3)
    l3 = pickle.loads(d3)

    assert l3._fields == r3._fields
    assert l3.__dict__ == r3.__dict__
