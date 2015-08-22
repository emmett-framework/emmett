# -*- coding: utf-8 -*-
"""
    weppy.tools.auth.handlers
    -------------------------

    Provides handlers for the authorization system.

    :copyright: (c) 2015 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

from datetime import timedelta
from ..._compat import itervalues
from ...dal import Field
from ...datastructures import sdict
from ...forms import Form
from ...globals import request, session
from ...handlers import Handler
from ...helpers import flash
from ...http import redirect
from ...language import T


class AuthLoginHandler(object):
    store_password = False
    create_user_onlogin = True
    next = None

    def __init__(self, auth, env=None):
        self.auth = auth
        self.env = env
        self.user = None

    def onsuccess(self):
        pass

    def get_user(self):
        return None


class DefaultLoginHandler(AuthLoginHandler):
    store_password = True
    create_user_onlogin = False

    def __init__(self, auth, env):
        AuthLoginHandler.__init__(self, auth, env)
        self.userfield = self.auth.settings.login_userfield
        # TODO: labels
        if self.userfield == 'email':
            self.loginfield = Field(
                validation={'is': 'email', 'presence': True}
            )
        else:
            v = {'presence': True}
            if self.auth.settings.username_case_sensitive:
                v['lower'] = True
            self.loginfield = Field(validation=v)
        passfield_valid = self.auth.settings.models.user.password._requires
        self.passfield = Field('password', validation=passfield_valid)
        self.rememberfield = Field(
            'bool', default=True, label=T('Remember me')
        )

    def get_user(self):
        return self.user

    def onaccept(self, form):
        userfield = self.userfield
        #passfield = self.passfield
        entered_username = form.vars[userfield]
        #if multi_login and '@' in entered_username:
        #   # if '@' in username check for email, not username
        #   user = self.table_user(email = entered_username)
        #else:
        user = self.auth.table_user(**{userfield: entered_username})
        if user:
            # user in db, check if registration pending or disabled
            temp_user = user
            if temp_user.registration_key == 'pending':
                flash(self.auth.messages.registration_pending)
                return
            elif temp_user.registration_key in ('disabled', 'blocked'):
                flash(self.auth.messages.login_disabled)
                return
            elif temp_user.registration_key is not None and \
                    temp_user.registration_key.strip():
                flash(self.auth.messages.registration_verifying)
                return
            #: verify password
            if form.vars.get('password', '') == temp_user.password:
                # success
                self.user = temp_user
        if not self.user:
            self.onfail()

    def onsuccess(self):
        flash(self.auth.messages.logged_in)

    def onfail(self):
        self.auth.log_event(self.auth.messages['login_failed_log'],
                            request.post_vars)
        flash(self.auth.messages.invalid_login)
        redirect(self.auth.url(args=['login'], vars=request.get_vars))

    def login_form(self):
        userfield = self.userfield
        form_fields = {
            userfield: self.loginfield,
            'password': self.passfield
        }
        if self.auth.settings.remember_me_form:
            form_fields['remember'] = self.rememberfield
        form = Form(
            form_fields,
            hidden=dict(_next=self.auth.settings.login_next),
            submit=self.auth.messages.login_button
        )
        '''
        captcha = settings.login_captcha or \
            (settings.login_captcha != False and settings.captcha)
        if captcha:
            addrow(form, captcha.label, captcha, captcha.comment,
                   settings.formstyle, 'captcha__row')
        '''
        if form.accepted:
            self.onaccept(form)
            ## rebuild the form
            if not self.user:
                return self.login_form()
        return form


class AuthManager(Handler):
    def __init__(self, auth):
        #: the Auth() instance
        self.auth = auth
        self._virtuals = []
        for field in itervalues(self.auth.settings.models.user.table):
            if isinstance(field, (Field.Virtual, Field.Method)):
                self._virtuals.append(field)

    @property
    def _user_as_row(self):
        r = sdict()
        r[self.auth.settings.table_user_name] = self.auth.user
        return r

    def _load_virtuals(self):
        #: inject virtual fields on session data
        for field in self._virtuals:
            if isinstance(field, Field.Virtual):
                try:
                    self.auth.user[field.name] = field.f(self._user_as_row)
                except:
                    pass
            if isinstance(field, Field.Method):
                try:
                    self.auth.user[field.name] = \
                        lambda s=self, field=field: field.f(s._user_as_row)
                except:
                    pass

    def on_start(self):
        # check auth session is valid
        if self.auth._auth and self.auth._auth.last_visit and \
           self.auth._auth.last_visit + \
           timedelta(days=0, seconds=self.auth._auth.expiration) > request.now:
            # load virtuals from Auth Model
            if self.auth.user:
                self._load_virtuals()
            # this is a trick to speed up sessions
            if (request.now - self.auth._auth.last_visit).seconds > \
               (self.auth._auth.expiration / 10):
                self.auth._auth.last_visit = request.now
        else:
            # if auth session is not valid and existent, delete it
            if self.auth._auth:
                del session.auth

    def on_end(self):
        # set correct session expiration if requested by user
        if self.auth._auth and self.auth._auth.remember:
            session._expires_after(self.auth._auth.expiration)
        # remove virtual fields
        if self.auth.user:
            ukeys = self.auth.user.keys()
            for field in self._virtuals:
                if field.name in ukeys:
                    del self.auth.user[field.name]
