# -*- coding: utf-8 -*-
"""
    tests.auth
    ----------

    Test weppy Auth module

    :copyright: (c) 2014-2016 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

import pytest
from weppy import App, sdict
from weppy.orm import Database, Field, Model, has_many, belongs_to
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
    db = Database(app, config=sdict(uri='sqlite:memory'))
    auth = Auth(app, db, user_model=User)
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
