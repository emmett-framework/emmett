# -*- coding: utf-8 -*-
"""
    weppy.tools.auth.handlers
    -------------------------

    Provides handlers for the authorization system.

    :copyright: (c) 2014-2016 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

from datetime import timedelta
from ...dal import Field
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
        entered_username = form.params[userfield]
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
            if form.params.get('password', '') == temp_user.password:
                # success
                self.user = temp_user
        if not self.user:
            self.onfail()

    def onsuccess(self):
        flash(self.auth.messages.logged_in)

    def onfail(self):
        self.auth.log_event(self.auth.messages['login_failed_log'],
                            request.body_params)
        flash(self.auth.messages.invalid_login)
        redirect(self.auth.url('login', request.query_params))

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
            #: rebuild the form
            if not self.user:
                return self.login_form()
        return form


class AuthManager(Handler):
    def __init__(self, auth):
        #: the Auth() instance
        self.auth = auth
        user_table = self.auth.settings.models.user.table
        self._virtuals = [f.name for f in user_table._virtual_fields]
        self._virtualmethods = [m.name for m in user_table._virtual_methods]

    def _load_virtuals(self):
        self.auth.settings.models.user._inject_virtuals_on_row(self.auth.user)

    def _unload_virtuals(self):
        for namelist in [self._virtuals, self._virtualmethods]:
            for name in namelist:
                try:
                    del self.auth.user[name]
                except:
                    pass

    def on_start(self):
        # check auth session is valid
        authsess = self.auth._auth
        if authsess:
            #: check session has needed data
            if not authsess.last_visit or not authsess.last_dbcheck:
                del session.auth
                return
            #: is session expired?
            if (authsess.last_visit +
               timedelta(seconds=authsess.expiration) < request.now):
                del session.auth
            #: does session need re-sync with db?
            elif authsess.last_dbcheck + timedelta(seconds=360) < request.now:
                if self.auth.user:
                    #: is user still valid?
                    dbrow = self.auth.table_user(id=self.auth.user.id)
                    if dbrow and not dbrow.registration_key:
                        self.auth.login_user(
                            self.auth.table_user(id=self.auth.user.id),
                            authsess.remember)
                    else:
                        del session.auth
            else:
                #: set last_visit if make sense
                if ((request.now - authsess.last_visit).seconds >
                   (authsess.expiration / 10)):
                    authsess.last_visit = request.now
        #: load virtuals from Auth Model
        if self.auth.user:
            self._load_virtuals()

    def on_end(self):
        # set correct session expiration if requested by user
        if self.auth._auth and self.auth._auth.remember:
            session._expires_after(self.auth._auth.expiration)
        # remove virtual fields for serialization
        if self.auth.user:
            self._unload_virtuals()
