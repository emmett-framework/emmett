# -*- coding: utf-8 -*-
"""
    tests.migrations
    ----------------

    Test Emmett migrations engine
"""

import uuid

import pytest

from emmett import App
from emmett.orm import Database, Model, Field, belongs_to, refers_to
from emmett.orm.migrations.engine import MetaEngine, Engine
from emmett.orm.migrations.generation import MetaData, Comparator


class FakeEngine(Engine):
    sql_history = []

    def _log_and_exec(self, sql):
        self.sql_history.append(sql)


@pytest.fixture(scope='module')
def app():
    rv = App(__name__)
    rv.config.db.uri = 'sqlite:memory'
    return rv


def _load_on_meta(ops):
    db = MetaData()
    engine = MetaEngine(db)
    for op in ops:
        op.engine = engine
        op.run()
    return db


def _make_ops(db, base=None):
    if base is not None:
        mdb = _load_on_meta(base.ops)
    else:
        mdb = MetaData()
    return Comparator.compare(db, mdb)


def _make_sql(db, op):
    engine = FakeEngine(db)
    op.engine = engine
    op.run()
    return engine.sql_history[-1] if engine.sql_history else None


class StepOneThing(Model):
    name = Field()
    value = Field.float()

_step_one_sql = """CREATE TABLE "step_one_things"(
    "id" INTEGER PRIMARY KEY AUTOINCREMENT,
    "name" CHAR(512),
    "value" DOUBLE
);"""

_step_one_sql_drop = 'DROP TABLE "step_one_things";'


def test_step_one_create_table(app):
    db = Database(app, auto_migrate=False)
    db.define_models(StepOneThing)
    ops = _make_ops(db)
    diffs = ops.as_diffs()
    assert len(diffs) == 1 and diffs[0][0] == "add_table"
    op = ops.ops[0]
    sql = _make_sql(db, op)
    assert sql == _step_one_sql


def test_step_one_no_diff_in_migration(app):
    db = Database(app, auto_migrate=False)
    db.define_models(StepOneThing)
    ops = _make_ops(db)
    ops2 = _make_ops(db, ops)
    assert len(ops2.as_diffs()) == 0


def test_step_one_drop_table(app):
    db = Database(app, auto_migrate=False)
    db.define_models(StepOneThing)
    ops = _make_ops(db)
    db2 = Database(app, auto_migrate=False)
    db2.define_models()
    ops2 = _make_ops(db2, ops)
    diffs = ops2.as_diffs()
    assert len(diffs) == 1 and diffs[0][0] == "remove_table"
    op = ops2.ops[0]
    sql = _make_sql(db2, op)
    assert sql == _step_one_sql_drop


class StepTwoThing(Model):
    name = Field(notnull=True)
    value = Field.float(default=8.8)
    available = Field.bool(default=True)

_step_two_sql = """CREATE TABLE "step_two_things"(
    "id" INTEGER PRIMARY KEY AUTOINCREMENT,
    "name" CHAR(512) NOT NULL,
    "value" DOUBLE DEFAULT '8.8',
    "available" CHAR(1) DEFAULT 'T'
);"""


def test_step_two_create_table(app):
    db = Database(app, auto_migrate=False)
    db.define_models(StepTwoThing)
    ops = _make_ops(db)
    op = ops.ops[0]
    sql = _make_sql(db, op)
    assert sql == _step_two_sql


class StepThreeThingOne(Model):
    a = Field()


class StepThreeThingTwo(Model):
    tablename = "step_three_thing_ones"
    a = Field()
    b = Field()


class StepThreeThingThree(Model):
    tablename = "step_three_thing_ones"
    b = Field()

_step_three_sql = 'ALTER TABLE "step_three_thing_ones" ADD "b" CHAR(512);'
_step_three_sql_drop = 'ALTER TABLE "step_three_thing_ones" DROP COLUMN "a";'


def test_step_three_create_column(app):
    db = Database(app, auto_migrate=False)
    db.define_models(StepThreeThingOne)
    ops = _make_ops(db)
    db2 = Database(app, auto_migrate=False)
    db2.define_models(StepThreeThingTwo)
    ops2 = _make_ops(db2, ops)
    op = ops2.ops[0]
    sql = _make_sql(db, op)
    assert sql == _step_three_sql


def test_step_three_drop_column(app):
    db = Database(app, auto_migrate=False)
    db.define_models(StepThreeThingTwo)
    ops = _make_ops(db)
    db2 = Database(app, auto_migrate=False)
    db2.define_models(StepThreeThingThree)
    ops2 = _make_ops(db2, ops)
    op = ops2.ops[0]
    sql = _make_sql(db, op)
    assert sql == _step_three_sql_drop


class StepFourThing(Model):
    name = Field(notnull=True)
    value = Field.float(default=8.8)
    available = Field.bool(default=True)
    asd = Field()


class StepFourThingEdit(Model):
    tablename = "step_four_things"
    name = Field()
    value = Field.float()
    available = Field.bool(default=True)
    asd = Field.int()

_step_four_sql = """ALTER TABLE "step_four_things" ALTER COLUMN "name" DROP NOT NULL;
ALTER TABLE "step_four_things" ALTER COLUMN "value" DROP DEFAULT;
ALTER TABLE "step_four_things" ALTER COLUMN "asd" TYPE INTEGER;"""


def test_step_four_alter_table(app):
    db = Database(app, auto_migrate=False)
    db.define_models(StepFourThing)
    ops = _make_ops(db)
    db2 = Database(app, auto_migrate=False)
    db2.define_models(StepFourThingEdit)
    ops2 = _make_ops(db2, ops)
    sql = []
    for op in ops2.ops:
        sql.append(_make_sql(db2, op))
    assert "\n".join(sql) == _step_four_sql


class StepFiveThing(Model):
    name = Field()
    code = Field(unique=True)
    value = Field.int()
    created_at = Field.datetime()

    indexes = {
        'name': True,
        ('name', 'value'): True
    }


class StepFiveThingEdit(StepFiveThing):
    tablename = "step_five_things"

    indexes = {
        'name': False,
        'name_created': {
            'fields': 'name',
            'expressions': lambda m: m.created_at.coalesce(None)}
    }


_step_five_sql_before = [
    'CREATE UNIQUE INDEX "step_five_things_widx__code_unique" ON "step_five_things" ("code");',
    'CREATE INDEX "step_five_things_widx__name" ON "step_five_things" ("name");',
    'CREATE INDEX "step_five_things_widx__name_value" ON "step_five_things" ("name","value");'
]

_step_five_sql_after = [
    'DROP INDEX "step_five_things_widx__name";',
    'CREATE INDEX "step_five_things_widx__name_created" ON "step_five_things" ("name",COALESCE("created_at",NULL));'
]


def test_step_five_indexes(app):
    db = Database(app, auto_migrate=False)
    db.define_models(StepFiveThing)
    ops = _make_ops(db)
    index_ops = ops.ops[1:]
    for op in index_ops:
        sql = _make_sql(db, op)
        assert sql in _step_five_sql_before
    db2 = Database(app, auto_migrate=False)
    db2.define_models(StepFiveThingEdit)
    ops2 = _make_ops(db2, ops)
    for op in ops2.ops:
        sql = _make_sql(db, op)
        assert sql in _step_five_sql_after


class StepSixThing(Model):
    id = Field()
    name = Field()

    default_values = {"id": lambda: uuid.uuid4()}


class StepSixRelate(Model):
    belongs_to('step_six_thing')
    name = Field()


_step_six_sql_t1 = """CREATE TABLE "step_six_things"(
    "id" CHAR(512) PRIMARY KEY,
    "name" CHAR(512)
);"""
_step_six_sql_t2 = """CREATE TABLE "step_six_relates"(
    "id" INTEGER PRIMARY KEY AUTOINCREMENT,
    "name" CHAR(512),
    "step_six_thing" CHAR(512)
);"""
_step_six_sql_fk = "".join([
    'ALTER TABLE "step_six_relates" ADD CONSTRAINT ',
    '"step_six_relates_ecnt__fk__stepsixthings_stepsixthing" FOREIGN KEY ',
    '("step_six_thing") REFERENCES "step_six_things"("id") ON DELETE CASCADE;'
])


def test_step_six_id_types(app):
    db = Database(app, auto_migrate=False)
    db.define_models(StepSixThing, StepSixRelate)
    ops = _make_ops(db)

    assert _make_sql(db, ops.ops[0]) == _step_six_sql_t1
    assert _make_sql(db, ops.ops[1]) == _step_six_sql_t2
    assert _make_sql(db, ops.ops[2]) == _step_six_sql_fk


class StepSevenThing(Model):
    primary_keys = ['foo', 'bar']

    foo = Field()
    bar = Field()


class StepSevenRelate(Model):
    refers_to({'foo': 'StepSevenThing.foo'}, {'bar': 'StepSevenThing.bar'})
    name = Field()

    foreign_keys = {
        "test": {
            "fields": ["foo", "bar"],
            "foreign_fields": ["foo", "bar"]
        }
    }


_step_seven_sql_t1 = """CREATE TABLE "step_seven_things"(
    "foo" CHAR(512),
    "bar" CHAR(512),
    PRIMARY KEY("foo", "bar")
);"""
_step_seven_sql_t2 = """CREATE TABLE "step_seven_relates"(
    "id" INTEGER PRIMARY KEY AUTOINCREMENT,
    "name" CHAR(512),
    "foo" CHAR(512),
    "bar" CHAR(512)
);"""
_step_seven_sql_fk = "".join([
    'ALTER TABLE "step_seven_relates" ADD CONSTRAINT ',
    '"step_seven_relates_ecnt__fk__stepseventhings_foo_bar" FOREIGN KEY ("foo","bar") ',
    'REFERENCES "step_seven_things"("foo","bar") ON DELETE CASCADE;',
])


def test_step_seven_composed_pks(app):
    db = Database(app, auto_migrate=False)
    db.define_models(StepSevenThing, StepSevenRelate)
    ops = _make_ops(db)

    assert _make_sql(db, ops.ops[0]) == _step_seven_sql_t1
    assert _make_sql(db, ops.ops[1]) == _step_seven_sql_t2
    assert _make_sql(db, ops.ops[2]) == _step_seven_sql_fk
