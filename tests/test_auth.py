# -*- coding: utf-8 -*-
"""
    tests.auth
    ----------

    Test weppy Auth module

    :copyright: (c) 2014-2016 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

import os
import pytest
import shutil
from weppy import App
from weppy.orm import Database, Field, Model, has_many, belongs_to
from weppy.sessions import SessionCookieManager
from weppy.tools import Auth, Mailer
from weppy.tools.auth.models import AuthUser


class User(AuthUser):
    has_many('things')
    gender = Field()


class Thing(Model):
    belongs_to('user')


@pytest.fixture(scope='module')
def app():
    rv = App(__name__)
    rv.config.mailer.sender = 'nina@massivedynamics.com'
    rv.config.auth.single_template = True
    rv.config.auth.hmac_key = "foobar"
    rv.pipeline = [SessionCookieManager('foobar')]
    return rv


@pytest.fixture(scope='module')
def client(app):
    return app.test_client()


@pytest.fixture(scope='module')
def mailer(app):
    return Mailer(app)


@pytest.fixture(scope='module')
def _db(app):
    try:
        shutil.rmtree(os.path.join(app.root_path, 'databases'))
    except:
        pass
    db = Database(app)
    app.pipeline.append(db.pipe)
    return db


@pytest.fixture(scope='module')
def auth(app, _db, mailer):
    auth = Auth(app, _db, user_model=User)
    app.pipeline.append(auth.pipe)
    authroutes = auth.module(__name__)
    return auth


@pytest.fixture(scope='module')
def db(_db, auth):
    _db.define_models(Thing)
    return _db


def test_models(db):
    user = User.create(
        email="walter@massivedynamics.com",
        password="pocketuniverse",
        first_name="Walter",
        last_name="Bishop"
    )
    group = db.auth_groups.insert(
        role="admin"
    )
    group2 = db.auth_groups.insert(
        role="moderator"
    )
    db.auth_memberships.insert(
        user=user.id,
        auth_group=group
    )
    db.auth_permissions.insert(
        auth_group=group
    )
    user = db.users[1]
    assert len(user.auth_memberships()) == 1
    assert user.auth_memberships()[0].user == 1
    assert len(user.auth_groups()) == 1
    assert user.auth_groups()[0].role == "admin"
    assert len(user.auth_permissions()) == 1
    assert user.auth_permissions()[0].auth_group.role == "admin"
    assert len(group.auth_memberships()) == 1
    assert group.auth_memberships()[0].auth_group == 1
    assert len(group.users()) == 1
    assert group.users()[0].email == "walter@massivedynamics.com"
    assert len(group.auth_permissions()) == 1
    user.auth_groups.add(group2)
    assert len(user.auth_groups(db.auth_groups.id)) == 2
    assert user.auth_groups(db.auth_groups.role)[1].role == "moderator"
    assert len(user.things()) == 0


def test_registration(mailer, db, client):
    page = client.get('/auth/registration').data
    assert 'Email' in page
    assert 'First Name' in page
    assert 'Last Name' in page
    assert 'Password' in page
    assert 'Confirm password' in page
    assert 'Register' in page
    with mailer.store_mails() as mailbox:
        with client.get('/auth/registration').context as ctx:
            req = client.post('/auth/registration', data={
                'email': 'william@massivedynamics.com',
                'first_name': 'William',
                'last_name': 'Bell',
                'password': 'imtheceo',
                'password2': 'imtheceo',
                '_csrf_token': list(ctx.session._csrf)[-1]
            }, follow_redirects=True)
            assert "We sent you an email, check your inbox" in req.data
        assert len(mailbox) == 1
        mail = mailbox[0]
        assert mail.recipients == ["william@massivedynamics.com"]
        assert mail.subject == 'Email verification'
        mail_as_str = str(mail)
        assert 'Hello william@massivedynamics.com!' in mail_as_str
        assert 'verify your email' in mail_as_str
        verification_code = mail_as_str.split(
            "http://localhost/auth/email_verification/")[1].split(" ")[0]
        req = client.get(
            '/auth/email_verification/{}'.format(verification_code),
            follow_redirects=True)
        assert "Account verification completed" in req.data


def test_login(mailer, db, client):
    page = client.get('/auth/login').data
    assert 'Email' in page
    assert 'Password' in page
    with client.get('/auth/login').context as ctx:
        req = client.post('/auth/login', data={
            'email': 'william@massivedynamics.com',
            'password': 'imtheceo',
            '_csrf_token': list(ctx.session._csrf)[-1]
        }, follow_redirects=True)
        assert 'William' in req.data
        assert 'Bell' in req.data
