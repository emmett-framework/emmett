# -*- coding: utf-8 -*-
"""
    tests.auth
    ----------

    Test weppy Auth module

    :copyright: (c) 2015 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

import pytest
from weppy import App, sdict
from weppy.dal import DAL, Field, Model, has_many, belongs_to
from weppy.tools import Auth
from weppy.tools.auth.models import AuthUser


class User(AuthUser):
    has_many('things')
    gender = Field()


class Thing(Model):
    belongs_to('user')


@pytest.fixture(scope='module')
def db():
    app = App(__name__)
    db = DAL(app, config=sdict(uri='sqlite:memory'))
    auth = Auth(app, db, usermodel=User)
    db.define_models(Thing)
    return db


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
        authgroup=group
    )
    db.auth_permissions.insert(
        authgroup=group
    )
    user = db.users[1]
    assert len(user.authmemberships()) == 1
    assert user.authmemberships()[0].user == 1
    assert len(user.authgroups()) == 1
    assert user.authgroups()[0].role == "admin"
    assert len(user.authpermissions()) == 1
    assert user.authpermissions()[0].authgroup.role == "admin"
    assert len(group.authmemberships()) == 1
    assert group.authmemberships()[0].authgroup == 1
    assert len(group.users()) == 1
    assert group.users()[0].email == "walter@massivedynamics.com"
    assert len(group.authpermissions()) == 1
    user.authgroups.add(group2)
    assert len(user.authgroups()) == 2
    assert user.authgroups()[1].role == "moderator"
    assert len(user.things()) == 0
