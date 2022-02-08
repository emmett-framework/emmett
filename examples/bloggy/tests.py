# -*- coding: utf-8 -*-

from multiprocessing import context
import pytest

from emmett import request, response, session, T
from emmett.orm.migrations.utils import generate_runtime_migration
from bloggy import app, db, User, auth, setup_admin


@pytest.fixture()
def client():
    return app.test_client()


@pytest.fixture(scope='module', autouse=True)
def _prepare_db(request):
    with db.connection():
        migration = generate_runtime_migration(db)
        migration.up()
        setup_admin()
    yield
    with db.connection():
        User.all().delete()
        auth.delete_group('admin')
        migration.down()


@pytest.fixture(scope='module')
def logged_client():
    c = app.test_client()
    with c.get('/auth/login').context as ctx:
        c.post('/auth/login', data={
            'email': 'doc@emmettbrown.com',
            'password': 'fluxcapacitor',
            '_csrf_token': list(ctx.session._csrf)[-1]
        }, follow_redirects=True)
        return c


def test_empty_db(client):
    r = client.get('/')
    assert 'No posts here so far' in r.data


def test_login(logged_client):
    r = logged_client.get('/')
    assert r.context.session.auth.user is not None


def test_no_admin_access(client):
    r = client.get('/new')
    assert r.context.response.status == 303


def test_admin_access(logged_client):
    r = logged_client.get('/new')
    assert r.context.response.status == 200
