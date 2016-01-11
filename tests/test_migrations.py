import os
import pytest
import shutil
from weppy import App
from weppy.dal import DAL, Model, Field
from weppy.dal.migrations.commands import generate, up


@pytest.fixture(scope='module')
def app():
    rv = App(__name__)
    rv.config.db.uri = 'sqlite:memory'
    return rv


def _list_migrations(app, revno_only=True):
    rv = []
    fnames = os.listdir(os.path.join(app.root_path, 'migrations'))
    for fname in fnames:
        if fname.split(".")[-1] == 'py':
            if revno_only:
                rv.append(fname.split("_")[0])
            else:
                rv.append(fname)
    return rv


def _erase_migrations(app):
    shutil.rmtree(os.path.join(app.root_path, 'migrations'))


def _last_sql(db, n=1):
    rv = []
    for q, t in db._timings[-n:]:
        rv.append(q)
    return rv if n > 1 else rv[0]


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
    generate(app, [db], 'test1', 'head')
    mrev = _list_migrations(app)[0]
    up(app, [db], mrev)
    sql = _last_sql(db)
    assert sql == _step_one_sql
    _erase_migrations(app)


class StepOneThingDiff(Model):
    name = Field()
    value = Field('float')


def test_step_one_no_diff_in_migration(app):
    db = DAL(app, auto_migrate=False)
    db.define_models(StepOneThingDiff)
    generate(app, [db], 'test1', 'head')
    mrev = _list_migrations(app)[0]
    up(app, [db], mrev)
    generate(app, [db], 'test_empty', 'head')
    revlist = _list_migrations(app, False)
    for i, rev in enumerate(revlist):
        if rev.startswith(mrev):
            continue
        nrev = rev
    with open(os.path.join(app.root_path, 'migrations', nrev)) as f:
        fdata = f.read()
    assert "def up(self):\n"+" "*8+"pass" in fdata
    assert "def down(self):\n"+" "*8+"pass" in fdata
    _erase_migrations(app)


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
    generate(app, [db], 'test1', 'head')
    mrev = _list_migrations(app)[0]
    up(app, [db], mrev)
    sql = _last_sql(db)
    assert sql == _step_two_sql
    _erase_migrations(app)
