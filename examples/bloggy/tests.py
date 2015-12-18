import pytest
from weppy import response, session
from bloggy import app, db, setup_admin


@pytest.fixture()
def client():
    return app.test_client()


@pytest.fixture(scope='module')
def logged_client():
    db._adapter.reconnect()
    setup_admin()
    c = app.test_client()
    with c.get('/account/login').context as ctx:
        c.post('/account/login', data={
            'email': 'walter@massivedynamics.com',
            'password': 'pocketuniverse',
            '_csrf_token': list(ctx.session._csrf)[-1]
        }, follow_redirects=True)
        return c


def test_empty_db(client):
    rv = client.get('/')
    assert 'No posts here so far' in rv.data


def test_login(logged_client):
    logged_client.get('/')
    assert session.auth.user is not None


def test_no_admin_access(client):
    client.get('/new')
    assert response.status == 303


def test_admin_access(logged_client):
    logged_client.get('/new')
    assert response.status == 200
