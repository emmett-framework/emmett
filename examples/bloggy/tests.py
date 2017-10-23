import pytest
from weppy import response, session
from bloggy import app, db, User, auth, setup_admin


@pytest.fixture()
def client():
    return app.test_client()


@pytest.fixture(scope='module', autouse=True)
def _prepare_db(request):
    with db.connection():
        setup_admin()
    yield
    with db.connection():
        User.all().delete()
        auth.delete_group('admin')


@pytest.fixture(scope='module')
def logged_client():
    c = app.test_client()
    with c.get('/auth/login').context as ctx:
        c.post('/auth/login', data={
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
