# -*- coding: utf-8 -*-
"""
    weppy.tools.auth.apis
    ---------------------

    Provides the interface for the authorization system.

    :copyright: (c) 2014-2017 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

from datetime import timedelta
from ..._compat import string_types, integer_types
from ..._internal import deprecated
from ...globals import session, request
from ...pipeline import Pipe
from .ext import AuthExtension
from .exposer import AuthModule


class Auth(object):
    def __init__(self, app, db, user_model=None):
        app.use_extension(AuthExtension)
        self.ext = app.ext.AuthExtension
        self.ext.bind_auth(self)
        self.ext.use_database(db, user_model)
        self.ext.init_forms()
        self.pipe = AuthPipe(self)

    def module(
        self, import_name, name='auth', template_folder='auth',
        template_path=None, url_prefix='auth', hostname=None, root_path=None,
        module_class=AuthModule
    ):
        return module_class.from_app(
            self.ext.app, import_name, name, template_folder, template_path,
            url_prefix, hostname, root_path
        )

    @property
    def models(self):
        return self.ext.config.models

    def group_for_role(self, role):
        return self.models['group'].get(role=role)

    #: context
    @property
    def session(self):
        return session.auth

    @property
    def user(self):
        try:
            rv = self.session.user
        except:
            rv = None
        return rv

    #: helpers
    def is_logged(self):
        return True if self.user else False

    @deprecated('is_logged_in', 'is_logged', 'Auth')
    def is_logged_in(self):
        return self.is_logged()

    def has_membership(self, group=None, user=None, role=None):
        rv = False
        if not group and role:
            group = self.group_for_role(role)
        if isinstance(group, string_types):
            group = self.group_for_role(group)
        if not user and self.user:
            user = self.user.id
        if group and user:
            if self.models['membership'].where(
                lambda m:
                    (m.table[self.ext.relation_names['user']] == user) &
                    (m.table[self.ext.relation_names['group']] == group)
            ).count():
                rv = True
        return rv

    def has_permission(
        self, name='any', table_name=None, record_id=None, user=None,
        group=None
    ):
        permission = self.models['permission']
        parent = None
        query = (permission.name == name)
        if table_name:
            query = query & (permission.table_name == table_name)
        if record_id:
            query = query & (permission.record_id == record_id)
        if not user and self.user:
            user = self.user.id
        if not user and not group:
            return False
        if user is not None:
            parent = self.models['user'].get(id=user)
        elif group is not None:
            if isinstance(group, string_types):
                group = self.group_for_role(group)
            parent = self.models['group'].get(id=group)
        if not parent:
            return False
        return (
            parent[self.ext.relation_names['permission'] + 's'].where(
                query).count() > 0)

    #: operations
    def create_group(self, role, description=''):
        res = self.models['group'].create(
            role=role, description=description)
        return res.id

    def delete_group(self, group):
        if isinstance(group, string_types):
            group = self.group_for_role(group)
        return self.ext.db(self.models['group'].id == group).delete()

    def add_membership(self, group, user=None):
        if isinstance(group, integer_types):
            group = self.models['group'].get(group)
        elif isinstance(group, string_types):
            group = self.group_for_role(group)
        if not user and self.user:
            user = self.user.id
        res = getattr(
            group, self.ext.relation_names['user'] + 's').add(user)
        return res.id

    def remove_membership(self, group, user=None):
        if isinstance(group, integer_types):
            group = self.models['group'].get(group)
        elif isinstance(group, string_types):
            group = self.group_for_role(group)
        if not user and self.user:
            user = self.user.id
        return getattr(
            group, self.ext.relation_names['user'] + 's').remove(user)

    def login(self, email, password):
        user = self.models['user'].get(email=email)
        if user and user.get('password', False):
            password = self.models['user'].password.validate(password)[0]
            if not user.registration_key and password == user.password:
                self.ext.login_user(user)
                return user
        return None

    def change_user_status(self, user, status):
        return self.ext.db(self.models['user'].id == user).update(
            registration_key=status)

    def disable_user(self, user):
        return self.change_user_status(user, 'disabled')

    def block_user(self, user):
        return self.change_user_status(user, 'blocked')

    def allow_user(self, user):
        return self.change_user_status(user, '')

    #: emails decorators
    def registration_mail(self, f):
        self.ext.mails['registration'] = f
        return f

    def reset_password_mail(self, f):
        self.ext.mails['reset_password'] = f
        return f


class AuthPipe(Pipe):
    def __init__(self, auth):
        #: the Auth() instance
        self.auth = auth

    def open(self):
        # check auth session is valid
        authsess = self.auth.session
        if not authsess:
            return
        #: check session has needed data
        if not authsess.last_visit or not authsess.last_dbcheck:
            del session.auth
            return
        #: is session expired?
        if (
            authsess.last_visit + timedelta(seconds=authsess.expiration) <
            request.now
        ):
            del session.auth
        #: does session need re-sync with db?
        elif authsess.last_dbcheck + timedelta(seconds=360) < request.now:
            if self.auth.user:
                #: is user still valid?
                dbrow = self.auth.models['user'].get(self.auth.user.id)
                if dbrow and not dbrow.registration_key:
                    self.auth.ext.login_user(dbrow, authsess.remember)
                else:
                    del session.auth
        else:
            #: set last_visit if make sense
            if (
                (request.now - authsess.last_visit).seconds >
                (authsess.expiration / 10)
            ):
                authsess.last_visit = request.now

    def close(self):
        # set correct session expiration if requested by user
        if self.auth.session and self.auth.session.remember:
            session._expires_after(self.auth.session.expiration)
