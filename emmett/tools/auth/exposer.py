# -*- coding: utf-8 -*-
"""
    emmett.tools.auth.exposer
    -------------------------

    Provides the routes layer for the auth system.

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

from __future__ import annotations

from typing import Any, List, Optional

from ...app import App, AppModule
from ...cache import RouteCacheRule
from ...helpers import flash, stream_dbfile
from ...http import redirect
from ...locals import request, session
from ...pipeline import Injector, Pipe, RequirePipe
from ...routing.urls import url


class AuthModule(AppModule):
    def __init__(
        self,
        app: App,
        name: str,
        import_name: str,
        template_folder: Optional[str] = None,
        template_path: Optional[str] = None,
        static_folder: Optional[str] = None,
        static_path: Optional[str] = None,
        url_prefix: Optional[str] = None,
        hostname: Optional[str] = None,
        cache: Optional[RouteCacheRule] = None,
        root_path: Optional[str] = None,
        pipeline: Optional[List[Pipe]] = None,
        injectors: Optional[List[Injector]] = None,
        **kwargs: Any
    ):
        super().__init__(
            app=app,
            name=name,
            import_name=import_name,
            template_folder=template_folder,
            template_path=template_path,
            static_folder=static_folder,
            static_path=static_path,
            url_prefix=url_prefix,
            hostname=hostname,
            cache=cache,
            root_path=root_path,
            pipeline=pipeline,
            injectors=injectors,
            **kwargs
        )
        self.init()

    def init(self):
        self.ext = self.app.ext.AuthExtension
        self.auth = self.ext.auth
        self.config = self.ext.config
        self._callbacks = {
            'after_login': self._after_login,
            'after_logout': self._after_logout,
            'after_registration': self._after_registration,
            'after_profile': self._after_profile,
            'after_email_verification': self._after_email_verification,
            'after_password_retrieval': self._after_password_retrieval,
            'after_password_reset': self._after_password_reset,
            'after_password_change': self._after_password_change
        }
        auth_pipe = [] if not self.config.inject_pipe else [self.auth.pipe]
        requires_login = [
            RequirePipe(
                lambda: self.auth.is_logged(),
                lambda: redirect(self.url('login')))]
        self._methods_pipelines = {
            'login': [],
            'logout': auth_pipe + requires_login,
            'registration': [],
            'profile': auth_pipe + requires_login,
            'email_verification': [],
            'password_retrieval': [],
            'password_reset': [],
            'password_change': auth_pipe + requires_login,
            'download': []
            # 'not_authorized': []
        }
        self.enabled_routes = list(self.config.enabled_routes)
        for method_name in self.config.disabled_routes:
            self.enabled_routes.remove(method_name)
        for key in self.enabled_routes:
            wrapper = getattr(self, key)
            f = getattr(self, "_" + key)
            wrapper()(f)
        #: configure message flashing
        if self.config.flash_messages:
            self.flash = self._flash
        else:
            self.flash = lambda *args, **kwargs: None
        #: register exposer to extensions
        self.ext.bind_exposer(self)

    def _template_for(self, key):
        tname = 'auth' if self.config.single_template else key
        return '{}{}'.format(tname, self.app.template_default_extension)

    def url(self, path, *args, **kwargs):
        path = "{}.{}".format(self.name, path)
        return url(path, *args, **kwargs)

    def _flash(self, message):
        return flash(message, 'auth')

    #: routes
    async def _login(self):
        def _validate_form(form):
            row = self.config.models['user'].get(email=form.params.email)
            if row:
                #: verify password
                if form.params.password == row.password:
                    res['user'] = row
                    return
            form.errors.email = self.config.messages['login_invalid']

        rv = {'message': None}
        res = {}
        rv['form'] = await self.ext.forms.login(onvalidation=_validate_form)
        if rv['form'].accepted:
            messages = self.config.messages
            if res['user'].registration_key == 'pending':
                rv['message'] = messages['approval_pending']
            elif res['user'].registration_key in ('disabled', 'blocked'):
                rv['message'] = messages['login_disabled']
            elif (
                res['user'].registration_key is not None and
                res['user'].registration_key.strip()
            ):
                rv['message'] = messages['verification_pending']
            if rv['message']:
                self.flash(rv['message'])
            else:
                self.ext.login_user(
                    res['user'], rv['form'].params.get('remember', False))
                self.ext.log_event(
                    self.config.messages['login_log'], {'id': res['user'].id})
                redirect_after = (await request.body_params)._after
                if redirect_after:
                    redirect(redirect_after)
                self._callbacks['after_login'](rv['form'])
        return rv

    async def _logout(self):
        self.ext.log_event(
            self.config.messages['logout_log'], {'id': self.auth.user.id})
        session.auth = None
        self.flash(self.config.messages['logged_out'])
        redirect_after = request.query_params._after
        if redirect_after:
            redirect(redirect_after)
        self._callbacks['after_logout']()

    async def _registration(self):
        def _validate_form(form):
            if form.params.password.password != form.params.password2.password:
                form.errors.password = "password mismatch"
                form.errors.password2 = "password mismatch"
                return
            del form.params.password2
            res['id'] = self.config.models['user'].table.insert(
                **form.params)

        rv = {'message': None}
        res = {}
        rv['form'] = await self.ext.forms.registration(
            onvalidation=_validate_form)
        if rv['form'].accepted:
            logged_in = False
            row = self.config.models['user'].get(res['id'])
            if self.config.registration_verification:
                email_data = {
                    'link': self.url(
                        'email_verification', row.registration_key,
                        scheme=True)}
                if not self.ext.mails['registration'](row, email_data):
                    rv['message'] = self.config.messages['mail_failure']
                    self.ext.db.rollback()
                    self.flash(rv['message'])
                    return rv
                rv['message'] = self.config.messages['mail_success']
                self.flash(rv['message'])
            elif self.config.registration_approval:
                rv['message'] = self.config.messages['approval_pending']
                self.flash(rv['message'])
            else:
                rv['message'] = self.config.messages['registration_success']
                self.flash(rv['message'])
                self.ext.login_user(row)
                logged_in = True
                self.ext.log_event(
                    self.config.messages['registration_log'],
                    {'id': res['id']})
            redirect_after = (await request.body_params)._after
            if redirect_after:
                redirect(redirect_after)
            self._callbacks['after_registration'](rv['form'], row, logged_in)
        return rv

    async def _profile(self):
        rv = {'message': None, 'form': await self.ext.forms.profile()}
        if rv['form'].accepted:
            self.auth.user.update(
                self.config.models['user'].table._filter_fields(
                    rv['form'].params))
            rv['message'] = self.config.messages['profile_updated']
            self.flash(rv['message'])
            self.ext.log_event(
                self.config.messages['profile_log'], {'id': self.auth.user.id})
            redirect_after = (await request.body_params)._after
            if redirect_after:
                redirect(redirect_after)
            self._callbacks['after_profile'](rv['form'])
        return rv

    async def _email_verification(self, key):
        rv = {'message': None}
        user = self.config.models['user'].get(registration_key=key)
        if not user:
            redirect(self.url('login'))
        if self.config.registration_approval:
            user.update_record(registration_key='pending')
            rv['message'] = self.config.messages['approval_pending']
            self.flash(rv['message'])
        else:
            user.update_record(registration_key='')
            rv['message'] = self.config.messages['verification_success']
            self.flash(rv['message'])
        #: make sure session has same user.registration_key as db record
        if self.auth.user:
            self.auth.user.registration_key = user.registration_key
        self.ext.log_event(
            self.config.messages['email_verification_log'], {'id': user.id})
        redirect_after = request.query_params._after
        if redirect_after:
            redirect(redirect_after)
        self._callbacks['after_email_verification'](user)
        return rv

    async def _password_retrieval(self):
        def _validate_form(form):
            messages = self.config.messages
            row = self.config.models['user'].get(email=form.params.email)
            if not row:
                form.errors.email = "invalid email"
                return
            if row.registration_key == 'pending':
                form.errors.email = messages['approval_pending']
                return
            if row.registration_key == 'blocked':
                form.errors.email = messages['login_disabled']
                return
            res['user'] = row

        rv = {'message': None}
        res = {}
        rv['form'] = await self.ext.forms.password_retrieval(
            onvalidation=_validate_form)
        if rv['form'].accepted:
            user = res['user']
            reset_key = self.ext.generate_reset_key(user)
            email_data = {
                'link': self.url(
                    'password_reset', reset_key, scheme=True)}
            if not self.ext.mails['reset_password'](user, email_data):
                rv['message'] = self.config.messages['mail_failure']
            rv['message'] = self.config.messages['mail_success']
            self.flash(rv['message'])
            self.ext.log_event(
                self.config.messages['password_retrieval_log'],
                {'id': user.id},
                user=user)
            redirect_after = (await request.body_params)._after
            if redirect_after:
                redirect(redirect_after)
            self._callbacks['after_password_retrieval'](user)
        return rv

    async def _password_reset(self, key):
        def _validate_form(form):
            if form.params.password.password != form.params.password2.password:
                form.errors.password = "password mismatch"
                form.errors.password2 = "password mismatch"

        rv = {'message': None}
        redirect_after = request.query_params._after
        user = self.ext.get_user_by_reset_key(key)
        if not user:
            rv['message'] = self.config.messages['reset_key_invalid']
            self.flash(rv['message'])
            if redirect_after:
                redirect(redirect_after)
            self._callbacks['after_password_reset'](user)
            return rv
        rv['form'] = await self.ext.forms.password_reset(
            onvalidation=_validate_form)
        if rv['form'].accepted:
            user.update_record(
                password=str(rv['form'].params.password),
                registration_key='',
                reset_password_key=''
            )
            rv['message'] = self.config.messages['password_changed']
            self.flash(rv['message'])
            self.ext.log_event(
                self.config.messages['password_reset_log'],
                {'id': user.id},
                user=user)
            if redirect_after:
                redirect(redirect_after)
            self._callbacks['after_password_reset'](user)
        return rv

    async def _password_change(self):
        def _validate_form(form):
            messages = self.config.messages
            if form.params.old_password != row.password:
                form.errors.old_password = messages['invalid_password']
                return
            if (
                form.params.new_password.password !=
                form.params.new_password2.password
            ):
                form.errors.new_password = "password mismatch"
                form.errors.new_password2 = "password mismatch"

        rv = {'message': None}
        row = self.config.models['user'].get(self.auth.user.id)
        rv['form'] = await self.ext.forms.password_change(
            onvalidation=_validate_form)
        if rv['form'].accepted:
            row.update_record(password=str(rv['form'].params.new_password))
            rv['message'] = self.config.messages['password_changed']
            self.flash(rv['message'])
            self.ext.log_event(
                self.config.messages['password_change_log'],
                {'id': row.id})
            redirect_after = request.query_params._after
            if redirect_after:
                redirect(redirect_after)
            self._callbacks['after_password_change']()
        return rv

    def _download(self, file_name):
        stream_dbfile(self.ext.db, file_name)

    #: routes decorators
    def login(self, template=None, pipeline=None, injectors=None):
        pipeline = self._methods_pipelines['login'] + (pipeline or [])
        return self.route(
            self.config['routes_paths']['login'], name='login',
            template=template or self._template_for('login'),
            pipeline=pipeline, injectors=injectors or [])

    def logout(self, template=None, pipeline=None, injectors=None):
        pipeline = self._methods_pipelines['logout'] + (pipeline or [])
        return self.route(
            self.config['routes_paths']['logout'], name='logout',
            template=template or self._template_for('logout'),
            pipeline=pipeline, injectors=injectors or [], methods='get')

    def registration(self, template=None, pipeline=None, injectors=None):
        pipeline = self._methods_pipelines['registration'] + (pipeline or [])
        return self.route(
            self.config['routes_paths']['registration'], name='registration',
            template=template or self._template_for('registration'),
            pipeline=pipeline, injectors=injectors or [])

    def profile(self, template=None, pipeline=None, injectors=None):
        pipeline = self._methods_pipelines['profile'] + (pipeline or [])
        return self.route(
            self.config['routes_paths']['profile'], name='profile',
            template=template or self._template_for('profile'),
            pipeline=pipeline, injectors=injectors or [])

    def email_verification(self, template=None, pipeline=None, injectors=None):
        pipeline = self._methods_pipelines['email_verification'] + (pipeline or [])
        return self.route(
            self.config['routes_paths']['email_verification'],
            name='email_verification',
            template=template or self._template_for('email_verification'),
            pipeline=pipeline, injectors=injectors or [], methods='get')

    def password_retrieval(self, template=None, pipeline=None, injectors=None):
        pipeline = self._methods_pipelines['password_retrieval'] + (pipeline or [])
        return self.route(
            self.config['routes_paths']['password_retrieval'],
            name='password_retrieval',
            template=template or self._template_for('password_retrieval'),
            pipeline=pipeline, injectors=injectors or [])

    def password_reset(self, template=None, pipeline=None, injectors=None):
        pipeline = self._methods_pipelines['password_reset'] + (pipeline or [])
        return self.route(
            self.config['routes_paths']['password_reset'],
            name='password_reset',
            template=template or self._template_for('password_reset'),
            pipeline=pipeline, injectors=injectors or [])

    def password_change(self, template=None, pipeline=None, injectors=None):
        pipeline = self._methods_pipelines['password_change'] + (pipeline or [])
        return self.route(
            self.config['routes_paths']['password_change'],
            name='password_change',
            template=template or self._template_for('password_change'),
            pipeline=pipeline, injectors=injectors or [])

    def download(self, template=None, pipeline=None, injectors=None):
        pipeline = self._methods_pipelines['download'] + (pipeline or [])
        return self.route(
            self.config['routes_paths']['download'], name='download',
            pipeline=pipeline, injectors=injectors or [], methods='get')

    #: callbacks
    def _after_login(self, form):
        redirect(self.url("profile"))

    def _after_logout(self):
        redirect(self.url("login"))

    def _after_registration(self, form, user, logged_in):
        if logged_in:
            redirect(self.url("profile"))
        redirect(self.url("login"))

    def _after_profile(self, form):
        redirect(self.url("profile"))

    def _after_email_verification(self, user):
        redirect(self.url("login"))

    def _after_password_retrieval(self, user):
        redirect(self.url("password_retrieval"))

    def _after_password_reset(self, user):
        redirect(self.url("login"))

    def _after_password_change(self):
        redirect(self.url("profile"))

    #: callbacks decorators
    def after_login(self, f):
        self._callbacks['after_login'] = f
        return f

    def after_logout(self, f):
        self._callbacks['after_logout'] = f
        return f

    def after_registration(self, f):
        self._callbacks['after_registration'] = f
        return f

    def after_profile(self, f):
        self._callbacks['after_profile'] = f
        return f

    def after_email_verification(self, f):
        self._callbacks['after_email_verification'] = f
        return f

    def after_password_retrieval(self, f):
        self._callbacks['after_password_retrieval'] = f
        return f

    def after_password_reset(self, f):
        self._callbacks['after_password_reset'] = f
        return f

    def after_password_change(self, f):
        self._callbacks['after_password_change'] = f
        return f
