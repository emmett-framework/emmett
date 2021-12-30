# -*- coding: utf-8 -*-
"""
    tests.orm_pks
    -------------

    Test ORM primary keys hendling
"""

import pytest

from uuid import uuid4

from emmett import App, sdict
from emmett.orm import Database, Model, Field
from emmett.orm.errors import SaveException
from emmett.orm.migrations.utils import generate_runtime_migration


class Standard(Model):
    foo = Field.string()
    bar = Field.string()


class CustomType(Model):
    id = Field.string()
    foo = Field.string()
    bar = Field.string()


class CustomName(Model):
    primary_keys = ["foo"]
    foo = Field.string()
    bar = Field.string()


class CustomMulti(Model):
    primary_keys = ["foo", "bar"]
    foo = Field.string()
    bar = Field.string()
    baz = Field.string()


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
    db.define_models(
        Standard,
        CustomType,
        CustomName,
        CustomMulti
    )
    return db

@pytest.fixture(scope='function')
def db(_db):
    migration = generate_runtime_migration(_db)
    migration.up()
    yield _db
    migration.down()


def test_insert(db):
    res = db.Standard.insert(foo="test1", bar="test2")
    assert isinstance(res, int)
    assert res.id
    assert res.foo == "test1"
    assert res.bar == "test2"

    res = db.CustomType.insert(id="test1", foo="test2", bar="test3")
    assert isinstance(res, str)
    assert res.id == "test1"
    assert res.foo == "test2"
    assert res.bar == "test3"

    res = db.CustomName.insert(foo="test1", bar="test2")
    assert isinstance(res, str)
    assert not res.id
    assert res.foo == "test1"
    assert res.bar == "test2"

    res = db.CustomMulti.insert(foo="test1", bar="test2", baz="test3")
    assert isinstance(res, tuple)
    assert not res.id
    assert res.foo == "test1"
    assert res.bar == "test2"
    assert res.baz == "test3"


def test_save_insert(db):
    row = Standard.new(foo="test1", bar="test2")
    done = row.save()
    assert done
    assert row._concrete
    assert row.id
    assert type(row.id) == int

    row = CustomType.new(id="test1", foo="test2", bar="test3")
    done = row.save()
    assert done
    assert row._concrete
    assert row.id == "test1"

    row = CustomName.new(foo="test1", bar="test2")
    done = row.save()
    assert done
    assert row._concrete
    assert "id" not in row
    assert row.foo == "test1"

    row = CustomMulti.new(foo="test1", bar="test2", baz="test3")
    done = row.save()
    assert done
    assert row._concrete
    assert "id" not in row
    assert row.foo == "test1"
    assert row.bar == "test2"
    assert row.baz == "test3"


def test_save_update(db):
    row = Standard.new(foo="test1", bar="test2")
    row.save()
    row.bar = "test2a"
    done = row.save()
    assert done
    assert row._concrete
    assert row.bar == "test2a"
    row.id = 123
    done = row.save()
    assert not done
    with pytest.raises(SaveException):
        row.save(raise_on_error=True)

    row = CustomType.new(id="test1", foo="test2", bar="test3")
    row.save()
    row.bar = "test2a"
    done = row.save()
    assert done
    assert row._concrete
    assert row.bar == "test2a"
    row.id = "test1a"
    done = row.save()
    assert not done
    with pytest.raises(SaveException):
        row.save(raise_on_error=True)

    row = CustomName.new(foo="test1", bar="test2")
    row.save()
    row.bar = "test2a"
    done = row.save()
    assert done
    assert row._concrete
    assert row.bar == "test2a"
    row.foo = "test1a"
    done = row.save()
    assert not done
    with pytest.raises(SaveException):
        row.save(raise_on_error=True)

    row = CustomMulti.new(foo="test1", bar="test2", baz="test3")
    row.save()
    row.baz = "test3a"
    done = row.save()
    assert done
    assert row._concrete
    assert row.baz == "test3a"
    row.foo = "test1a"
    done = row.save()
    assert not done
    with pytest.raises(SaveException):
        row.save(raise_on_error=True)


def test_destroy_delete(db):
    row = Standard.new(foo="test1", bar="test2")
    row.save()
    done = row.destroy()
    assert done
    assert not row._concrete
    assert row.id is None
    assert row.foo == "test1"

    row = CustomType.new(id="test1", foo="test2", bar="test3")
    row.save()
    done = row.destroy()
    assert done
    assert not row._concrete
    assert row.id is None
    assert row.foo == "test2"

    row = CustomName.new(foo="test1", bar="test2")
    row.save()
    done = row.destroy()
    assert done
    assert not row._concrete
    assert row.foo is None
    assert row.bar == "test2"

    row = CustomMulti.new(foo="test1", bar="test2", baz="test3")
    row.save()
    done = row.destroy()
    assert done
    assert not row._concrete
    assert row.foo is None
    assert row.bar is None
    assert row.baz == "test3"
