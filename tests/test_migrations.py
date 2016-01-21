import pytest
from weppy import App
from weppy.dal import DAL, Model, Field
from weppy.dal.migrations.engine import MetaEngine, Engine
from weppy.dal.migrations.generation import MetaData, Comparator


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
    op.engine = FakeEngine(db)
    op.run()
    return engine.sql_history[-1] if engine.sql_history else None


class StepOneThing(Model):
    name = Field()
    value = Field('float')

_step_one_sql = """CREATE TABLE step_one_things(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name CHAR(512),
    value DOUBLE
);"""


def test_step_one_create_table(app):
    db = DAL(app, auto_migrate=False)
    db.define_models(StepOneThing)
    ops = _make_ops(db)
    diffs = ops.as_diffs()
    assert len(diffs) == 1 and diffs[0][0] == "add_table"
    op = ops.ops[0]
    sql = _make_sql(db, op)
    assert sql == _step_one_sql


def test_step_one_no_diff_in_migration(app):
    db = DAL(app, auto_migrate=False)
    db.define_models(StepOneThing)
    ops = _make_ops(db)
    ops2 = _make_ops(db, ops)
    assert len(ops2.as_diffs()) == 0


class StepTwoThing(Model):
    name = Field(notnull=True)
    value = Field('float', default=8.8)
    available = Field('bool', default=True)

_step_two_sql = """CREATE TABLE step_two_things(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name CHAR(512) NOT NULL,
    value DOUBLE DEFAULT '8.8',
    available CHAR(1) DEFAULT 'T'
);"""


def test_step_two_create_table(app):
    db = DAL(app, auto_migrate=False)
    db.define_models(StepTwoThing)
    ops = _make_ops(db)
    op = ops.ops[0]
    sql = _make_sql(db, op)
    assert sql == _step_two_sql
