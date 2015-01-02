# -*- coding: utf-8 -*-
"""
    weppy.tools.auth
    ----------------

    Provides the authorization system.

    :copyright: (c) 2015 by Giovanni Barillari

    Based on the web2py's auth module (http://www.web2py.com)
    :copyright: (c) by Massimo Di Pierro <mdipierro@cs.depaul.edu>

    :license: LGPLv3 (http://www.gnu.org/licenses/lgpl.html)
"""

## NOTE for developers by gi0baro:
## This code is in alpha stage. It's very dirty.
## Stuffs I've missed (until now):
##    - captcha is not ported, but I want to
##    - CAS is not ported, but I want to
##    - impersonate() is not ported (want to?)
##    - ajax behaviours are missing, need to re-design the flow
##    - generally, all code needs a lot of cleaning
##    - maybe some flows can be optimized (since in web2py
##      everything was built on request, not here)

import urllib
from datetime import datetime, timedelta
from pydal.objects import Table, Field, Row, Set, Query
from ..globals import current, request, response, session
from ..datastructures import sdict
from ..http import HTTP, redirect
from ..forms import Form, DALForm
from ..tags import tag
from ..handlers import Handler
from ..security import uuid
from ..helpers import flash
from ..language import T
from . import Mail

DEFAULT = lambda: None


default_settings = dict(
    password_min_length=6,
    cas_maps=None,
    reset_password_requires_verification=False,
    registration_requires_verification=False,
    registration_requires_approval=False,
    login_after_registration=False,
    login_after_password_change=True,
    create_user_groups=None,
    everybody_group_id=None,
    #login_captcha=None,
    #register_captcha=None,
    #retrieve_username_captcha=None,
    #retrieve_password_captcha=None,
    #captcha=None,
    expiration=3600,  # one hour
    long_expiration=3600 * 30 * 24,  # one month
    remember_me_form=True,
    allow_basic_login=False,
    on_failed_authentication=lambda x: redirect(x),
    logging_enabled=True,
    allow_delete_accounts=False,
    password_field='password',
    table_user_name='auth_user',
    table_group_name='auth_group',
    table_membership_name='auth_membership',
    table_permission_name='auth_permission',
    table_event_name='auth_event',
    #table_cas_name='auth_cas',
    use_username=False,
    login_userfield='email',
    logout_onlogout=None,
    register_fields=None,
    profile_fields=None,
    email_case_sensitive=True,
    username_case_sensitive=True,
    update_fields=['email'],
    ondelete="CASCADE",
    extra_fields={},
    actions_disabled=[],
    login_onvalidation=[],
    login_onaccept=[],
    login_onfail=[],
    register_onvalidation=[],
    register_onaccept=[],
    verify_email_onaccept=[],
    profile_onvalidation=[],
    profile_onaccept=[],
    change_password_onvalidation=[],
    change_password_onaccept=[],
    retrieve_password_onvalidation=[],
    reset_password_onvalidation=[],
    reset_password_onaccept=[]
)

default_messages = dict(
    login_button='Login',
    register_button='Register',
    password_reset_button='Request reset password',
    password_change_button='Change password',
    profile_save_button='Apply changes',
    submit_button='Submit',
    verify_password='Verify Password',
    delete_label='Check to delete',
    function_disabled='Function disabled',
    access_denied='Insufficient privileges',
    registration_verifying='Registration needs verification',
    registration_pending='Registration is pending approval',
    email_taken='This email already has an account',
    invalid_username='Invalid username',
    username_taken='Username already taken',
    login_disabled='Login disabled by administrator',
    logged_in='Logged in',
    email_sent='Email sent',
    unable_to_send_email='Unable to send email',
    email_verified='Email verified',
    logged_out='Logged out',
    registration_successful='Registration successful',
    invalid_email='Invalid email',
    unable_send_email='Unable to send email',
    invalid_login='Invalid login',
    invalid_user='Invalid user',
    invalid_password='Invalid password',
    is_empty="Cannot be empty",
    mismatched_password="Password fields don't match",
    verify_email='Welcome %(username)s! Click on the link %(link)s to verify your email',
    verify_email_subject='Email verification',
    username_sent='Your username was emailed to you',
    new_password_sent='A new password was emailed to you',
    password_changed='Password changed',
    retrieve_username='Your username is: %(username)s',
    retrieve_username_subject='Username retrieve',
    retrieve_password='Your password is: %(password)s',
    retrieve_password_subject='Password retrieve',
    reset_password=
    'Click on the link %(link)s to reset your password',
    reset_password_subject='Password reset',
    invalid_reset_password='Invalid reset password',
    profile_updated='Profile updated',
    new_password='New password',
    old_password='Old password',
    group_description='Group uniquely assigned to user %(id)s',
    register_log='User %(id)s Registered',
    login_log='User %(id)s Logged-in',
    login_failed_log=None,
    logout_log='User %(id)s Logged-out',
    profile_log='User %(id)s Profile updated',
    verify_email_log='User %(id)s Verification email sent',
    retrieve_username_log='User %(id)s Username retrieved',
    retrieve_password_log='User %(id)s Password retrieved',
    reset_password_log='User %(id)s Password reset',
    change_password_log='User %(id)s Password changed',
    add_group_log='Group %(group_id)s created',
    del_group_log='Group %(group_id)s deleted',
    add_membership_log=None,
    del_membership_log=None,
    has_membership_log=None,
    add_permission_log=None,
    del_permission_log=None,
    has_permission_log=None,
    impersonate_log='User %(id)s is impersonating %(other_id)s',
    label_first_name='First name',
    label_last_name='Last name',
    label_username='Username',
    label_email='E-mail',
    label_password='Password',
    label_registration_key='Registration key',
    label_reset_password_key='Reset Password key',
    label_registration_id='Registration identifier',
    label_role='Role',
    label_description='Description',
    label_user_id='User ID',
    label_group_id='Group ID',
    label_name='Name',
    label_table_name='Object or table name',
    label_record_id='Record ID',
    label_time_stamp='Timestamp',
    label_client_ip='Client IP',
    label_origin='Origin',
    label_remember_me="Remember me (for 30 days)",
    verify_password_comment='please input your password again',
)


class Auth(object):
    """
    Class for authentication, authorization, role based access control.

    Includes:

    - registration and profile
    - login and logout
    - username and password retrieval
    - event logging
    - role creation and assignment
    - user defined group/role based permission

    exposes:

    - http://.../{base_url}/login
    - http://.../{base_url}/logout
    - http://.../{base_url}/register
    - http://.../{base_url}/verify_email
    - http://.../{base_url}/retrieve_username
    - http://.../{base_url}/retrieve_password
    - http://.../{base_url}/reset_password
    - http://.../{base_url}/change_password
    - http://.../{base_url}/profile

    """
    registered_actions = {}

    def get_or_create_key(self, app, filename=None, alg='sha512'):
        import os
        if not filename:
            path = os.path.join(app.root_path, 'private')
            if not os.path.exists(path):
                os.mkdir(path)
            filename = os.path.join(path, 'auth.key')
        else:
            filename = os.path.join(app.root_path, filename)
        if os.path.exists(filename):
            key = open(filename, 'r').read().strip()
        else:
            key = alg + ':' + uuid()
            open(filename, 'w').write(key)
        return key

    def url(self, args=[], vars=None, scheme=False):
        q = urllib.quote
        u = self.settings.base_url
        if not isinstance(args, (list, tuple)):
            args = [args]
        u = u + '/' + '/'.join(q(a) for a in args)
        if vars:
            u = u + '?' + '&'.join('%s=%s' % (q(k), q(v))
                                   for k, v in vars.iteritems())
        return u

    def _init_usermodel(self, usermodel, use_signature):
        usermodel.auth = self
        usermodel.db = self.db
        #user = usermodel(_migrate, _fake_migrate, _use_signature)
        user = usermodel()
        self.define_tables(use_signature)
        user.entity = self.table_user
        # load user's definitions
        getattr(user, '_AuthModel__define')()
        # set reference in db for datamodel name
        setattr(self.db, usermodel.__name__, user.entity)
        self.entity = user.entity
        #if app.config.get('auth', {}).get('server', 'default') != "default":
        #    self.settings.mailer.server = app.config.auth.server
        #    self.settings.mailer.sender = app.config.auth.sender
        #    self.settings.mailer.login = app.config.auth.login

    def __init__(self, app, db, usermodel=None, mailer=True, hmac_key=None,
                 hmac_key_file=None, signature=True, base_url=None,
                 csrf_prevention=True, **kwargs):
        """
        auth=Auth(app, db)

        - db has to be the database where to create tables for authentication
        - mailer=Mail(...) or None (no mailed) or True (make a mailer)
        - hmac_key can be a hmac_key or hmac_key=Auth.get_or_create_key()
        - base_url (where is the user action?)
        - cas_provider (delegate authentication to the URL, CAS2)
        """
        self.db = db
        self.csrf_prevention = csrf_prevention

        if hmac_key is None:
            hmac_key = self.get_or_create_key(app, hmac_key_file)

        url_index = base_url or "/account"
        url_login = url_index + "/login"

        settings = self.settings = sdict()
        settings.update(default_settings)
        settings.update(
            base_url=url_index,
            #cas_domains=[request.env.http_host],
            #cas_provider=cas_provider,
            #cas_actions=dict(login='login',
            #                validate='validate',
            #                servicevalidate='serviceValidate',
            #                proxyvalidate='proxyValidate',
            #                logout='logout'),
            login_url=url_login,
            logged_url=url_index+"/profile",
            download_url="/download",
            mailer=(mailer == True) and Mail(app) or mailer,
            on_failed_authorization = url_index+"/not_authorized",
            login_next = url_index+"/profile",
            login_methods = [self],
            login_form = self,
            logout_next = url_index,
            register_next = url_index,
            verify_email_next = url_login,
            profile_next = url_index,
            retrieve_username_next = url_index,
            retrieve_password_next = url_index,
            request_reset_password_next = url_login,
            reset_password_next = url_index,
            change_password_next = url_index,
            hmac_key = hmac_key
        )
        #: load user's settings
        for key, value in app.config.auth.items():
            if key in self.settings.keys():
                self.settings[key] = value

        # ## these are messages that can be customized
        messages = self.messages = sdict()
        messages.update(default_messages)

        if signature:
            self.define_signature()
        else:
            self.signature = None

        #: define allowed actions
        default_actions = [
            'login', 'logout', 'register', 'verify_email',
            'retrieve_username', 'retrieve_password',
            'reset_password', 'request_reset_password',
            'change_password', 'profile', 'groups',
            #'impersonate',
            'not_authorized']
        for k in default_actions:
            if k not in self.settings.actions_disabled:
                self.register_action(k, getattr(self, k))

        _use_signature = kwargs.get('sign_tables')
        if usermodel:
            from ..dal import AuthModel
            if not issubclass(usermodel, AuthModel):
                raise RuntimeError('%s is an invalid user model' %
                                   usermodel.__name__)
            self._init_usermodel(usermodel, _use_signature)
        else:
            self.define_tables(_use_signature)

    @property
    def _auth(self):
        return session.auth

    @property
    def user(self):
        try:
            u = session.auth.user if session.auth.user else None
        except:
            u = None
        return u

    def get_vars_next(self):
        next = request.vars._next
        if isinstance(next, (list, tuple)):
            next = next[0]
        return next

    @property
    def user_id(self):
        "accessor for auth.user_id"
        return self.user and self.user.id or None

    @property
    def table_user(self):
        return self.db[self.settings.table_user_name]

    @property
    def table_group(self):
        return self.db[self.settings.table_group_name]

    @property
    def table_membership(self):
        return self.db[self.settings.table_membership_name]

    @property
    def table_permission(self):
        return self.db[self.settings.table_permission_name]

    @property
    def table_event(self):
        return self.db[self.settings.table_event_name]

    #@property
    #def table_cas(self):
    #   return self.db[self.settings.table_cas_name]

    @property
    def handler(self):
        return AuthManager(self)

    def register_action(self, name, f):
        self.registered_actions[name] = f

    def __call__(self, f, a):
        """
        usage:

        def authentication(): return dict(form=auth())
        """

        if not f:
            redirect(self.url(args='login', vars=request.vars))
        elif f in self.settings.actions_disabled:
            raise HTTP(404)
        if f in self.registered_actions:
            if a is not None:
                return self.registered_actions[f](a)
            else:
                return self.registered_actions[f]()
        else:
            raise HTTP(404)

    def __get_migrate(self, tablename, migrate=True):
        if type(migrate).__name__ == 'str':
            return (migrate + tablename + '.table')
        elif migrate == False:
            return False
        else:
            return True

    def enable_record_versioning(self, tables, archive_db=None,
                                 archive_names='%(tablename)s_archive',
                                 current_record='current_record',
                                 current_record_label=None):
        """
        to enable full record versioning (including auth tables):

        auth = Auth(db)
        auth.define_tables(signature=True)
        # define our own tables
        db.define_table('mything',Field('name'),auth.signature)
        auth.enable_record_versioning(tables=db)

        tables can be the db (all table) or a list of tables.
        only tables with modified_by and modified_on fiels (as created
        by auth.signature) will have versioning. Old record versions will be
        in table 'mything_archive' automatically defined.

        when you enable enable_record_versioning, records are never
        deleted but marked with is_active=False.

        enable_record_versioning enables a common_filter for
        every table that filters out records with is_active = False

        Important: If you use auth.enable_record_versioning,
        do not use auth.archive or you will end up with duplicates.
        auth.archive does explicitly what enable_record_versioning
        does automatically.

        """
        current_record_label = current_record_label or T(
            current_record.replace('_', ' ').title())
        for table in tables:
            fieldnames = table.fields()
            if 'id' in fieldnames and 'modified_on' in fieldnames and \
               not current_record in fieldnames:
                table._enable_record_versioning(
                    archive_db=archive_db,
                    archive_name=archive_names,
                    current_record=current_record,
                    current_record_label=current_record_label)

    def define_signature(self):
        settings = self.settings
        reference_user = 'reference %s' % settings.table_user_name

        def lazy_user(auth=self):
            return auth.user_id

        def represent(id, record=None, s=settings):
            try:
                user = s.table_user(id)
                return '%s %s' % (user.get("first_name", user.get("email")),
                                  user.get("last_name", ''))
            except:
                return id
        ondelete = self.settings.ondelete
        self.signature = Table(
            self.db, 'auth_signature',
            Field('is_active', 'boolean',
                  default=True,
                  readable=False, writable=False,
                  label='Is Active'),
            Field('created_on', 'datetime',
                  default=lambda: datetime.now(),
                  writable=False, readable=False,
                  label='Created On'),
            Field('created_by',
                  reference_user,
                  default=lazy_user, represent=represent,
                  writable=False, readable=False,
                  label='Created By', ondelete=ondelete),
            Field('modified_on', 'datetime',
                  update=lambda: datetime.now(),
                  default=lambda: datetime.now(),
                  writable=False, readable=False,
                  label='Modified On'),
            Field('modified_by',
                  reference_user, represent=represent,
                  default=lazy_user, update=lazy_user,
                  writable=False, readable=False,
                  label='Modified By',  ondelete=ondelete))

    def define_tables(self, signature=None, migrate=None, fake_migrate=None):
        """
        to be called unless tables are defined manually

        usages:

            # defines all needed tables and table files
            # 'myprefix_auth_user.table', ...
            auth.define_tables(migrate='myprefix_')

            # defines all needed tables without migration/table files
            auth.define_tables(migrate=False)

        """
        from ..validators import isntEmpty, Crypt, isEmail, notInDb, Lower, \
            Matches, isIntInRange
        db = self.db
        if migrate is None:
            migrate = db._migrate
        if fake_migrate is None:
            fake_migrate = db._fake_migrate
        settings = self.settings
        if not self.signature:
            self.define_signature()
        if signature == True:
            signature_list = [self.signature]
        elif not signature:
            signature_list = []
        elif isinstance(signature, Table):
            signature_list = [signature]
        else:
            signature_list = signature
        is_not_empty = isntEmpty(error_message=self.messages.is_empty)
        is_crypted = Crypt(key=settings.hmac_key,
                           min_length=settings.password_min_length)
        is_unique_email = [
            isEmail(error_message=self.messages.invalid_email),
            notInDb(db, '%s.email' % settings.table_user_name,
                         error_message=self.messages.email_taken)]
        if not settings.email_case_sensitive:
            is_unique_email.insert(1, Lower())
        if not settings.table_user_name in db.tables:
            passfield = settings.password_field
            extra_fields = settings.extra_fields.get(
                settings.table_user_name, []) + signature_list
            if settings.use_username or settings.cas_provider:
                is_unique_username = \
                    [Matches('[\w\.\-]+', strict=True,
                              error_message=self.messages.invalid_username),
                     notInDb(db, '%s.username' % settings.table_user_name,
                                  error_message=self.messages.username_taken)]
                if not settings.username_case_sensitive:
                    is_unique_username.insert(1, Lower())
                db.define_table(
                    settings.table_user_name,
                    Field('first_name', length=128, default='',
                          label=self.messages.label_first_name,
                          requires=is_not_empty),
                    Field('last_name', length=128, default='',
                          label=self.messages.label_last_name,
                          requires=is_not_empty),
                    Field('email', length=512, default='',
                          label=self.messages.label_email,
                          requires=is_unique_email),
                    Field('username', length=128, default='',
                          label=self.messages.label_username,
                          requires=is_unique_username),
                    Field(passfield, 'password', length=512,
                          readable=False, label=self.messages.label_password,
                          requires=[is_crypted]),
                    Field('registration_key', length=512,
                          writable=False, readable=False, default='',
                          label=self.messages.label_registration_key),
                    Field('reset_password_key', length=512,
                          writable=False, readable=False, default='',
                          label=self.messages.label_reset_password_key),
                    Field('registration_id', length=512,
                          writable=False, readable=False, default='',
                          label=self.messages.label_registration_id),
                    *extra_fields,
                    **dict(
                        migrate=self.__get_migrate(settings.table_user_name,
                                                   migrate),
                        fake_migrate=fake_migrate,
                        format='%(username)s'))
            else:
                db.define_table(
                    settings.table_user_name,
                    Field('first_name', length=128, default='',
                          label=self.messages.label_first_name,
                          requires=is_not_empty),
                    Field('last_name', length=128, default='',
                          label=self.messages.label_last_name,
                          requires=is_not_empty),
                    Field('email', length=512, default='',
                          label=self.messages.label_email,
                          requires=is_unique_email),
                    Field(passfield, 'password', length=512,
                          readable=False, label=self.messages.label_password,
                          requires=[is_crypted]),
                    Field('registration_key', length=512,
                          writable=False, readable=False, default='',
                          label=self.messages.label_registration_key),
                    Field('reset_password_key', length=512,
                          writable=False, readable=False, default='',
                          label=self.messages.label_reset_password_key),
                    Field('registration_id', length=512,
                          writable=False, readable=False, default='',
                          label=self.messages.label_registration_id),
                    *extra_fields,
                    **dict(
                        migrate=self.__get_migrate(settings.table_user_name,
                                                   migrate),
                        fake_migrate=fake_migrate,
                        format='%(first_name)s %(last_name)s (%(id)s)'))
        reference_table_user = 'reference %s' % settings.table_user_name
        if not settings.table_group_name in db.tables:
            extra_fields = settings.extra_fields.get(
                settings.table_group_name, []) + signature_list
            db.define_table(
                settings.table_group_name,
                Field(
                    'role', length=512, default='',
                    label=self.messages.label_role,
                    requires=notInDb(
                        db, '%s.role' % settings.table_group_name)),
                Field('description', 'text',
                      label=self.messages.label_description),
                *extra_fields,
                **dict(
                    migrate=self.__get_migrate(
                        settings.table_group_name, migrate),
                    fake_migrate=fake_migrate,
                    format='%(role)s (%(id)s)'))
        reference_table_group = 'reference %s' % settings.table_group_name
        if not settings.table_membership_name in db.tables:
            extra_fields = settings.extra_fields.get(
                settings.table_membership_name, []) + signature_list
            db.define_table(
                settings.table_membership_name,
                Field('user_id', reference_table_user,
                      label=self.messages.label_user_id),
                Field('group_id', reference_table_group,
                      label=self.messages.label_group_id),
                *extra_fields,
                **dict(
                    migrate=self.__get_migrate(
                        settings.table_membership_name, migrate),
                    fake_migrate=fake_migrate))
        if not settings.table_permission_name in db.tables:
            extra_fields = settings.extra_fields.get(
                settings.table_permission_name, []) + signature_list
            db.define_table(
                settings.table_permission_name,
                Field('group_id', reference_table_group,
                      label=self.messages.label_group_id),
                Field('name', default='default', length=512,
                      label=self.messages.label_name,
                      requires=is_not_empty),
                Field('table_name', length=512,
                      label=self.messages.label_table_name),
                Field('record_id', 'integer', default=0,
                      label=self.messages.label_record_id,
                      requires=isIntInRange(0, 10 ** 9)),
                *extra_fields,
                **dict(
                    migrate=self.__get_migrate(
                        settings.table_permission_name, migrate),
                    fake_migrate=fake_migrate))
        if not settings.table_event_name in db.tables:
            db.define_table(
                settings.table_event_name,
                Field('time_stamp', 'datetime',
                      default=lambda: datetime.now(),
                      label=self.messages.label_time_stamp),
                Field('client_ip',
                      default=lambda: request.client if
                      hasattr(current, 'request') else 'unavailable',
                      label=self.messages.label_client_ip),
                Field('user_id', reference_table_user, default=None,
                      label=self.messages.label_user_id),
                Field('origin', default='auth', length=512,
                      label=self.messages.label_origin,
                      requires=is_not_empty),
                Field('description', 'text', default='',
                      label=self.messages.label_description,
                      requires=is_not_empty),
                *settings.extra_fields.get(settings.table_event_name, []),
                **dict(
                    migrate=self.__get_migrate(
                        settings.table_event_name, migrate),
                    fake_migrate=fake_migrate))
        #if settings.cas_domains:
        #    if not settings.table_cas_name in db.tables:
        #        db.define_table(
        #            settings.table_cas_name,
        #            Field('user_id', reference_table_user, default=None,
        #                  label=self.messages.label_user_id),
        #            Field('created_on', 'datetime', default=lambda: datetime.now()),
        #            Field('service', requires=IS_URL()),
        #            Field('ticket'),
        #            Field('renew', 'boolean', default=False),
        #            *settings.extra_fields.get(settings.table_cas_name, []),
        #            **dict(
        #                migrate=self.__get_migrate(
        #                    settings.table_cas_name, migrate),
        #                fake_migrate=fake_migrate))

        #if settings.cas_provider:  # THIS IS NOT LAZY
        #   settings.actions_disabled = \
        #       ['profile', 'register', 'change_password',
        #        'request_reset_password', 'retrieve_username']
        #   from gluon.contrib.login_methods.cas_auth import CasAuth
        #   maps = settings.cas_maps
        #   if not maps:
        #       table_user = self.table_user()
        #       maps = dict((name, lambda v, n=name: v.get(n, None)) for name in
        #                   table_user.fields if name != 'id'
        #                   and table_user[name].readable)
        #       maps['registration_id'] = \
        #           lambda v, p=settings.cas_provider: '%s/%s' % (p, v['user'])
        #   actions = [settings.cas_actions['login'],
        #              settings.cas_actions['servicevalidate'],
        #              settings.cas_actions['logout']]
        #   settings.login_form = CasAuth(
        #       casversion=2,
        #       urlbase=settings.cas_provider,
        #       actions=actions,
        #       maps=maps)
        return self

    def log_event(self, description, vars=None, origin='auth'):
        """
        usage:

            auth.log_event(description='this happened', origin='auth')
        """
        if not self.settings.logging_enabled or not description:
            return
        elif self.is_logged_in():
            user_id = self.user.id
        else:
            user_id = None  # user unknown
        vars = vars or {}
        # log messages should not be translated
        if type(description).__name__ == 'TElement':
            description = description.m
        self.table_event.insert(
            description=str(description % vars),
            origin=origin, user_id=user_id)

    def get_or_create_user(self, keys, update_fields=['email'],
                           login=True, get=True):
        """
        Used for alternate login methods:
            If the user exists already then password is updated.
            If the user doesn't yet exist, then they are created.
        """
        #table_user = self.table_user()
        user = None
        checks = []
        # make a guess about who this user is
        for fieldname in ['registration_id', 'username', 'email']:
            if fieldname in self.table_user.fields() and \
                    keys.get(fieldname, None):
                checks.append(fieldname)
                value = keys[fieldname]
                user = self.table_user(**{fieldname: value})
                if user:
                    break
        if not checks:
            return None
        if not 'registration_id' in keys:
            keys['registration_id'] = keys[checks[0]]
        # if we think we found the user but registration_id does not match,
        # make new user
        if 'registration_id' in checks and user and user.registration_id \
           and ('registration_id' not in keys or user.registration_id !=
                str(keys['registration_id'])):
            user = None  # THINK MORE ABOUT THIS? DO WE TRUST OPENID PROVIDER?
        if user:
            if not get:
                # added for register_bare to avoid overwriting users
                return None
            update_keys = dict(registration_id=keys['registration_id'])
            for key in update_fields:
                if key in keys:
                    update_keys[key] = keys[key]
            user.update_record(**update_keys)
        elif checks:
            if not 'first_name' in keys and 'first_name' in \
               self.table_user.fields:
                guess = keys.get('email', 'anonymous').split('@')[0]
                keys['first_name'] = keys.get('username', guess)
            user_id = self.table_user.insert(
                **self.table_user._filter_fields(keys))
            user = self.table_user[user_id]
            if self.settings.create_user_groups:
                group_id = self.add_group(
                    self.settings.create_user_groups % user)
                self.add_membership(group_id, user_id)
            if self.settings.everybody_group_id:
                self.add_membership(self.settings.everybody_group_id, user_id)
            if login:
                self.login_user(user)
        return user

    def basic(self, basic_auth_realm=False):
        """
        perform basic login.

        :param basic_auth_realm: optional basic http authentication realm.
        :type basic_auth_realm: str or unicode or function or callable or boolean.

        reads current.request.env.http_authorization
        and returns basic_allowed,basic_accepted,user.

        if basic_auth_realm is defined is a callable it's return value
        is used to set the basic authentication realm, if it's a string
        its content is used instead.  Otherwise basic authentication realm
        is set to the application name.
        If basic_auth_realm is None or False (the default) the behavior
        is to skip sending any challenge.

        """
        import base64
        if not self.settings.allow_basic_login:
            return (False, False, False)
        basic = request.env.http_authorization
        if basic_auth_realm:
            if callable(basic_auth_realm):
                basic_auth_realm = basic_auth_realm()
            elif isinstance(basic_auth_realm, (unicode, str)):
                basic_realm = unicode(basic_auth_realm)
            elif basic_auth_realm is True:
                basic_realm = u'' + request.application
            http_401 = HTTP(
                401, u'Not Authorized',
                **{'WWW-Authenticate': u'Basic realm="' + basic_realm + '"'})
        if not basic or not basic[:6].lower() == 'basic ':
            if basic_auth_realm:
                raise http_401
            return (True, False, False)
        (username, sep, password) = base64.b64decode(basic[6:]).partition(':')
        is_valid_user = sep and self.login_bare(username, password)
        if not is_valid_user and basic_auth_realm:
            raise http_401
        return (True, True, is_valid_user)

    def login_user(self, user):
        """
        login the user = db.auth_user(id)
        """
        user = Row(user)
        for key, value in user.items():
            if callable(value) or key == 'password':
                delattr(user, key)
        session.auth = sdict(
            user=user,
            last_visit=request.now,
            expiration=self.settings.expiration,
            hmac_key=uuid())
        self.update_groups()

    def _get_login_settings(self):
        userfield = self.settings.login_userfield or 'username' \
            if 'username' in self.table_user.fields else 'email'
        passfield = self.settings.password_field
        return sdict({"table_user": self.table_user,
                        "userfield": userfield,
                        "passfield": passfield})

    def login_bare(self, username, password):
        """
        logins user as specified by username (or email) and password
        """
        settings = self._get_login_settings()
        user = self.table_user(**{settings.userfield: username})
        if user and user.get(settings.passfield, False):
            password = self.table_user[settings.passfield].validate(
                password)[0]
            if not user.registration_key and password == \
               user[settings.passfield]:
                self.login_user(user)
                return user
        else:
            # user not in database try other login methods
            for login_method in self.settings.login_methods:
                if login_method != self and \
                   login_method(username, password):
                    self.user = username
                    return username
        return False

    def register_bare(self, **fields):
        """
        registers a user as specified by username (or email)
        and a raw password.
        """
        settings = self._get_login_settings()
        if not fields.get(settings.passfield):
            raise ValueError("register_bare: " +
                             "password not provided or invalid")
        elif not fields.get(settings.userfield):
            raise ValueError("register_bare: " +
                             "userfield not provided or invalid")
        fields[settings.passfield] = \
            self.table_user[settings.passfield].validate(
                fields[settings.passfield])[0]
        user = self.get_or_create_user(
            fields, login=False, get=False,
            update_fields=self.settings.update_fields)
        if not user:
            # get or create did not create a user (it ignores
            # duplicate records)
            return False
        return user

    def _login_with_handler(self, handler, env=None):
        if not issubclass(handler, AuthLoginHandler):
            raise RuntimeError('Provided handler for login is invalid')

        settings = self.settings
        passfield = settings.password_field
        log = self.messages['login_log']

        # redirect user if it's already logged in
        if self.user:
            redirect(settings.login_next)

        handler = handler(self, env)

        # use session for federated login
        snext = self.get_vars_next()
        if snext:
            session._auth_next = snext
        elif session._auth_next:
            snext = session._auth_next

        if handler.next is None:
            unext = settings.login_next
            if snext:
                unext = snext
        else:
            unext = handler.next

        #: init handler form if required
        #  note: we need to load the form before calling `get_user()`, as the
        #        handler could use the form itself to init the user var
        loginform = None
        if hasattr(handler, 'login_form'):
            loginform = handler.login_form()
        #: get user from handler
        user = handler.get_user()
        if user:
            if not handler.store_password:
                user[passfield] = None
            if handler.create_user_onlogin:
                user = self.get_or_create_user(
                    self.table_user._filter_fields(user),
                    settings.update_fields)
        #: return form if required
        elif loginform is not None:
            return loginform
        #: use external login url
        else:
            redirect(handler.login_url(unext))

        #: process authenticated users
        user = Row(self.table_user._filter_fields(user, id=True))
        self.login_user(user)
        #: use the right session expiration
        session.auth.expiration = \
            request.vars.get('remember', False) and \
            settings.long_expiration or \
            settings.expiration
        session.auth.remember = 'remember' in request.vars
        #: log login
        self.log_event(log, user)
        #: handler callback
        handler.onsuccess()

        #: clean session next
        if unext == session._auth_next:
            del session._auth_next
        #: proceed
        redirect(unext)

    def login(self):
        return self._login_with_handler(DefaultLoginHandler)

    def logout(self, next=DEFAULT, onlogout=DEFAULT, log=DEFAULT):
        """
        logout and redirects to login

        method: Auth.logout ([next=DEFAULT[, onlogout=DEFAULT[,
            log=DEFAULT]]])

        """

        if next is DEFAULT:
            next = self.get_vars_next() or self.settings.logout_next
        if onlogout is DEFAULT:
            onlogout = self.settings.logout_onlogout
        if onlogout:
            onlogout(self.user)
        if log is DEFAULT:
            log = self.messages['logout_log']
        if self.user:
            self.log_event(log, self.user)
        if self.settings.login_form != self:
            cas = self.settings.login_form
            cas_user = cas.get_user()
            if cas_user:
                next = cas.logout_url(next)

        session.auth = None
        flash(self.messages.logged_out)
        if not next is None:
            redirect(next)

    def register(self, next=DEFAULT, onvalidation=DEFAULT, onaccept=DEFAULT,
                 log=DEFAULT):
        """
        returns a registration form

        method: Auth.register([next=DEFAULT [, onvalidation=DEFAULT
            [, onaccept=DEFAULT [, log=DEFAULT]]]])

        """
        def process_form(form):
            if form.vars.password.password != form.vars.password2:
                form.errors.password = "password mismatch"

        if self.is_logged_in():
            redirect(self.settings.logged_url)
        if next is DEFAULT:
            next = self.get_vars_next() or self.settings.register_next
        if onvalidation is DEFAULT:
            onvalidation = self.settings.register_onvalidation
        if onaccept is DEFAULT:
            onaccept = self.settings.register_onaccept
        if log is DEFAULT:
            log = self.messages['register_log']

        username = self.settings.login_userfield

        #: it think it's enoght with table definition
        # Ensure the username field is unique.
        #unique_validator = IS_NOT_IN_DB(self.db, self.table_user[username])
        #if not self.table_user[username].requires:
        #   self.table_user[username].requires = unique_validator
        #elif isinstance(self.table_user[username].requires, (list, tuple)):
        #   if not any([isinstance(validator, IS_NOT_IN_DB) for validator in
        #               self.table_user[username].requires]):
        #       if isinstance(self.table_user[username].requires, list):
        #           self.table_user[username].requires.append(unique_validator)
        #       else:
        #           self.table_user[username].requires += (unique_validator, )
        #elif not isinstance(self.table_user[username].requires, IS_NOT_IN_DB):
        #   self.table_user[username].requires = [self.table_user[username].requires,
        #                                    unique_validator]

        passfield = self.settings.password_field
        if not self.settings.register_fields:
            self.settings.register_fields = [
                field.name for field in self.table_user
                if field.type != 'id' and field.writable]
        form_fields = [field for field in self.table_user
                       if field.name in self.settings.register_fields]
        for i, field in enumerate(form_fields):
            if field.name == passfield:
                pass2 = Field(
                    'password2', 'password'
                )
                form_fields.insert(i+1, pass2)
                break
        form = Form(
            *form_fields,
            hidden=dict(_next=next),
            submit=self.messages.register_button,
            onvalidation=process_form,
            keepvalues=True
        )
        self.table_user.registration_key.default = key = uuid()
        if form.accepted:
            del form.vars['password2']
            form.vars.id = self.table_user.insert(**form.vars)
            description = self.messages.group_description % form.vars
            if self.settings.create_user_groups:
                group_id = self.add_group(
                    self.settings.create_user_groups % form.vars, description)
                self.add_membership(group_id, form.vars.id)
            if self.settings.everybody_group_id:
                self.add_membership(
                    self.settings.everybody_group_id, form.vars.id)
            if self.settings.registration_requires_verification:
                link = self.url(['verify_email', key], scheme=True)
                d = dict(request.vars)
                d.update(dict(key=key, link=link,
                         username=form.vars[username]))
                if not (self.settings.mailer and self.settings.mailer.send(
                        to=form.vars.email,
                        subject=self.messages.verify_email_subject,
                        message=self.messages.verify_email % d)):
                    self.db.rollback()
                    response.flash = self.messages.unable_send_email
                    return form
                flash(self.messages.email_sent)
            if self.settings.registration_requires_approval and \
               not self.settings.registration_requires_verification:
                self.table_user[form.vars.id] = dict(
                    registration_key='pending')
                flash(self.messages.registration_pending)
            elif (not self.settings.registration_requires_verification or
                    self.settings.login_after_registration):
                if not self.settings.registration_requires_verification:
                    self.table_user[form.vars.id] = dict(registration_key='')
                flash(self.messages.registration_successful)
                user = self.table_user(**{username: form.vars[username]})
                self.login_user(user)
                flash(self.messages.logged_in)
            self.log_event(log, form.vars)
            callback(onaccept, form)
            if not next:
                next = self.url('register')
            else:
                next = replace_id(next, form)
            redirect(next)
                    #client_side=self.settings.client_side)
        return form

    def is_logged_in(self):
        """
        checks if the user is logged in and returns True/False.
        if so user is in auth.user as well as in session.auth.user
        """

        if self.user:
            return True
        return False

    def verify_email(self, key, next=DEFAULT, onaccept=DEFAULT, log=DEFAULT):
        """
        action user to verify the registration email, XXXXXXXXXXXXXXXX

        method: Auth.verify_email([next=DEFAULT [, onvalidation=DEFAULT
            [, onaccept=DEFAULT [, log=DEFAULT]]]])

        """

        user = self.table_user(registration_key=key)
        if not user:
            redirect(self.settings.login_url)
        if self.settings.registration_requires_approval:
            user.update_record(registration_key='pending')
            flash(self.messages.registration_pending)
        else:
            user.update_record(registration_key='')
            flash(self.messages.email_verified)
        # make sure session has same user.registrato_key as db record
        if self.user:
            self.user.registration_key = user.registration_key
        if log is DEFAULT:
            log = self.messages['verify_email_log']
        if next is DEFAULT:
            next = self.settings.verify_email_next
        if onaccept is DEFAULT:
            onaccept = self.settings.verify_email_onaccept
        self.log_event(log, user)
        callback(onaccept, user)
        redirect(next)

    def retrieve_username(self, next=DEFAULT, onvalidation=DEFAULT,
                          onaccept=DEFAULT, log=DEFAULT):
        """
        returns a form to retrieve the user username
        (only if there is a username field)

        method: Auth.retrieve_username([next=DEFAULT
            [, onvalidation=DEFAULT [, onaccept=DEFAULT [, log=DEFAULT]]]])

        """
        from ..validators import inDb
        if not 'username' in self.table_user.fields:
            raise HTTP(404)
        #captcha = self.settings.retrieve_username_captcha or \
        #        (self.settings.retrieve_username_captcha != False and self.settings.captcha)
        if not self.settings.mailer:
            response.flash = self.messages.function_disabled
            return ''
        if next is DEFAULT:
            next = self.get_vars_next() or self.settings.retrieve_username_next
        if onvalidation is DEFAULT:
            onvalidation = self.settings.retrieve_username_onvalidation
        if onaccept is DEFAULT:
            onaccept = self.settings.retrieve_username_onaccept
        if log is DEFAULT:
            log = self.messages['retrieve_username_log']
        email_field = self.table_user.email.clone()
        email_field.requires = [
            inDb(self.db, self.table_user.email,
                 error_message=self.messages.invalid_email)]
        form = Form(
            email_field,
            hidden=dict(_next=next),
            sumbit=self.messages.submit_button
        )
        #if captcha:
        #   addrow(form, captcha.label, captcha,
        #          captcha.comment, self.settings.formstyle, 'captcha__row')

        if form.accepted:
            users = self.table_user._db(
                self.table_user.email == form.vars.email).select()
            if not users:
                flash(self.messages.invalid_email)
                redirect(self.url(args=request.args))
            username = ', '.join(u.username for u in users)
            self.settings.mailer.send(
                to=form.vars.email,
                subject=self.messages.retrieve_username_subject,
                message=self.messages.retrieve_username % dict(
                    username=username))
            flash(self.messages.email_sent)
            for user in users:
                self.log_event(log, user)
            callback(onaccept, form)
            if not next:
                next = self.url('retrieve_username')
            else:
                next = replace_id(next, form)
            redirect(next)
        return form

    def random_password(self):
        import string
        import random
        password = ''
        specials = r'!#$*'
        for i in range(0, 3):
            password += random.choice(string.lowercase)
            password += random.choice(string.uppercase)
            password += random.choice(string.digits)
            password += random.choice(specials)
        return ''.join(random.sample(password, len(password)))

    def reset_password(self, next=DEFAULT, onvalidation=DEFAULT,
                       onaccept=DEFAULT, log=DEFAULT):
        """
        returns a form to reset the user password

        method: Auth.reset_password([next=DEFAULT
            [, onvalidation=DEFAULT [, onaccept=DEFAULT [, log=DEFAULT]]]])

        """
        import time

        def _same_psw(value):
            if value != request.vars.new_password:
                return (value, mismatch_psw_msg)
            return (value, None)
        mismatch_psw_msg = self.messages.mismatched_password

        if next is DEFAULT:
            next = self.get_vars_next() or self.settings.reset_password_next
        try:
            key = request.vars.key
            t0 = int(key.split('-')[0])
            if time.time() - t0 > 60 * 60 * 24:
                raise Exception
            user = self.table_user(reset_password_key=key)
            if not user:
                raise Exception
        except Exception:
            flash(self.messages.invalid_reset_password)
            #redirect(next, client_side=self.settings.client_side)
            redirect(next)
        passfield = self.settings.password_field
        form = Form(
            Field(
                'new_password', 'password',
                label=self.messages.new_password,
                requires=self.table_user()[passfield].requires),
            Field(
                'new_password2', 'password',
                label=self.messages.verify_password,
                requires=[_same_psw]),
            submit=self.messages.password_reset_button,
            hidden=dict(_next=next),
        )
        if form.accepted:
            user.update_record(
                **{passfield: str(form.vars.new_password),
                   'registration_key': '',
                   'reset_password_key': ''})
            flash(self.messages.password_changed)
            if self.settings.login_after_password_change:
                self.login_user(user)
            redirect(next)
        return form

    def request_reset_password(self, next=DEFAULT, onvalidation=DEFAULT,
                               onaccept=DEFAULT, log=DEFAULT):
        """
        returns a form to reset the user password

        method: Auth.reset_password([next=DEFAULT
            [, onvalidation=DEFAULT [, onaccept=DEFAULT [, log=DEFAULT]]]])

        """
        from ..validators import isEmail, inDb
        #captcha = self.settings.retrieve_password_captcha or \
        #        (self.settings.retrieve_password_captcha != False and self.settings.captcha)

        if next is DEFAULT:
            next = self.get_vars_next() or self.settings.request_reset_password_next
        if not self.settings.mailer:
            response.flash = self.messages.function_disabled
            return ''
        if onvalidation is DEFAULT:
            onvalidation = self.settings.reset_password_onvalidation
        if onaccept is DEFAULT:
            onaccept = self.settings.reset_password_onaccept
        if log is DEFAULT:
            log = self.messages['reset_password_log']
        userfield = self.settings.login_userfield
        if userfield == 'email':
            req = [isEmail(error_message=self.messages.invalid_email),
                   inDb(self.db, self.table_user.email,
                        error_message=self.messages.invalid_email)]
        else:
            req = [inDb(self.db, self.table_user.username,
                        error_message=self.messages.invalid_username)]
        form_field = self.table_user[userfield].clone()
        form_field.requires = req
        form = Form(
            form_field,
            hidden=dict(_next=next),
            submit=self.messages.password_reset_button
        )
        #if captcha:
        #   addrow(form, captcha.label, captcha,
        #          captcha.comment, self.settings.formstyle, 'captcha__row')
        if form.accepted:
            user = self.table_user(**{userfield: form.vars.email})
            if not user:
                flash(self.messages['invalid_%s' % userfield])
                redirect(self.url('request_reset_password'))
            elif user.registration_key in ('pending', 'disabled', 'blocked'):
                flash(self.messages.registration_pending)
                redirect(self.url('request_reset_password'))
            if self.email_reset_password(user):
                flash(self.messages.email_sent)
            else:
                flash(self.messages.unable_to_send_email)
            self.log_event(log, user)
            callback(onaccept, form)
            if not next:
                redirect(self.url('request_reset_password'))
            else:
                next = replace_id(next, form)
            redirect(next)
        return form

    def email_reset_password(self, user):
        import time
        reset_password_key = str(int(time.time())) + '-' + uuid()
        link = self.url('reset_password', vars={"key": reset_password_key},
                        scheme=True)
        d = dict(user)
        d.update(dict(key=reset_password_key, link=link))
        if self.settings.mailer and self.settings.mailer.send(
           to=user.email,
           subject=self.messages.reset_password_subject,
           message=self.messages.reset_password % d):
            user.update_record(reset_password_key=reset_password_key)
            return True
        return False

    def retrieve_password(self, next=DEFAULT, onvalidation=DEFAULT,
                          onaccept=DEFAULT, log=DEFAULT):
        if self.settings.reset_password_requires_verification:
            return self.request_reset_password(next, onvalidation, onaccept,
                                               log)
        else:
            return self.reset_password(next, onvalidation, onaccept, log)

    def change_password(self, next=DEFAULT, onvalidation=DEFAULT,
                        onaccept=DEFAULT, log=DEFAULT):
        """
        returns a form that lets the user change password

        method: Auth.change_password([next=DEFAULT[, onvalidation=DEFAULT[,
            onaccept=DEFAULT[, log=DEFAULT]]]])
        """
        def _same_psw(value):
            if value != request.vars.new_password:
                return (value, mismatch_psw_msg)
            return (value, None)
        mismatch_psw_msg = self.messages.mismatched_password

        if not self.is_logged_in():
            redirect(self.settings.login_url,
                     client_side=self.settings.client_side)
        s = self.db(self.table_user.id == self.user.id)

        if next is DEFAULT:
            next = self.get_vars_next() or self.settings.change_password_next
        if onvalidation is DEFAULT:
            onvalidation = self.settings.change_password_onvalidation
        if onaccept is DEFAULT:
            onaccept = self.settings.change_password_onaccept
        if log is DEFAULT:
            log = self.messages['change_password_log']
        passfield = self.settings.password_field
        form = Form(
            Field('old_password', 'password',
                  label=self.messages.old_password,
                  requires=self.table_user[passfield].requires),
            Field('new_password', 'password',
                  label=self.messages.new_password,
                  requires=self.table_user[passfield].requires),
            Field(
                'new_password2', 'password',
                label=self.messages.verify_password,
                requires=[_same_psw]),
            submit=self.messages.password_change_button,
            hidden=dict(_next=next)
        )
        if form.accepted:
            if not form.vars['old_password'] == s.select(
               limitby=(0, 1), orderby_on_limitby=False).first()[passfield]:
                form.errors['old_password'] = self.messages.invalid_password
            else:
                d = {passfield: str(form.vars.new_password)}
                s.update(**d)
                flash(self.messages.password_changed)
                self.log_event(log, self.user)
                callback(onaccept, form)
                if not next:
                    next = self.url('change_password')
                else:
                    next = replace_id(next, form)
                redirect(next)
        return form

    def profile(self, next=DEFAULT, onvalidation=DEFAULT, onaccept=DEFAULT,
                log=DEFAULT):
        """
        returns a form that lets the user change his/her profile

        method: Auth.profile([next=DEFAULT [, onvalidation=DEFAULT
            [, onaccept=DEFAULT [, log=DEFAULT]]]])

        """

        if not self.is_logged_in():
            redirect(self.settings.login_url)
        passfield = self.settings.password_field
        if next is DEFAULT:
            next = self.get_vars_next() or self.settings.profile_next
        if onvalidation is DEFAULT:
            onvalidation = self.settings.profile_onvalidation
        if onaccept is DEFAULT:
            onaccept = self.settings.profile_onaccept
        if log is DEFAULT:
            log = self.messages['profile_log']
        if not self.settings.profile_fields:
            self.settings.profile_fields = [
                field.name for field in self.table_user
                if field.type != 'id' and field.writable]
        if passfield in self.settings.profile_fields:
            self.settings.profile_fields.remove(passfield)
        form = DALForm(
            self.table_user,
            record_id=self.user.id,
            fields=self.settings.profile_fields,
            hidden=dict(_next=next),
            submit=self.messages.profile_save_button,
            upload=self.settings.download_url)
        if form.accepted:
            self.user.update(self.table_user._filter_fields(form.vars))
            flash(self.messages.profile_updated)
            self.log_event(log, self.user)
            callback(onaccept, form)
            ## TO-DO: update this
            #if form.deleted:
            #   return self.logout()
            if not next:
                next = self.url('profile')
            else:
                next = replace_id(next, form)
            redirect(next)
        return form

    def run_login_onaccept(self):
        onaccept = self.settings.login_onaccept
        if onaccept:
            form = sdict(dict(vars=self.user))
            if not isinstance(onaccept, (list, tuple)):
                onaccept = [onaccept]
            for callback in onaccept:
                callback(form)

    def update_groups(self):
        if not self.user:
            return
        user_groups = {}
        if self._auth:
            self._auth.user_groups = user_groups
        memberships = self.db(
            self.table_membership.user_id == self.user.id).select()
        for membership in memberships:
            group = self.table_group(membership.group_id)
            if group:
                user_groups[membership.group_id] = group.role

    def groups(self):
        """
        displays the groups and their roles for the logged in user
        """
        if not self.is_logged_in():
            redirect(self.settings.login_url)
        memberships = self.db(
            self.table_membership.user_id == self.user.id).select()
        table = tag.table()
        for membership in memberships:
            groups = self.db(
                self.table_group.id == membership.group_id).select()
            if groups:
                group = groups[0]
                table.append(tag.tr(tag.h3(group.role, '(%s)' % group.id)))
                table.append(tag.tr(tag.p(group.description)))
        if not memberships:
            return None
        return table

    def not_authorized(self):
        """
        you can change the view for this page to make it look as you like
        """
        if request.isajax:
            raise HTTP(403, 'ACCESS DENIED')
        return 'ACCESS DENIED'

    def add_group(self, role, description=''):
        """
        creates a group associated to a role
        """

        group_id = self.table_group.insert(
            role=role, description=description)
        self.log_event(self.messages['add_group_log'],
                       dict(group_id=group_id, role=role))
        return group_id

    def del_group(self, group_id):
        """
        deletes a group
        """
        self.db(self.table_group.id == group_id).delete()
        self.db(self.table_membership.group_id == group_id).delete()
        self.db(self.table_permission.group_id == group_id).delete()
        self.update_groups()
        self.log_event(self.messages.del_group_log, dict(group_id=group_id))

    def id_group(self, role):
        """
        returns the group_id of the group specified by the role
        """
        rows = self.db(self.table_group.role == role).select()
        if not rows:
            return None
        return rows[0].id

    def user_group(self, user_id=None):
        """
        returns the group_id of the group uniquely associated to this user
        i.e. role=user:[user_id]
        """
        return self.id_group(self.user_group_role(user_id))

    def user_group_role(self, user_id=None):
        if not self.settings.create_user_groups:
            return None
        if user_id:
            user = self.table_user[user_id]
        else:
            user = self.user
        return self.settings.create_user_groups % user

    def has_membership(self, group_id=None, user_id=None, role=None):
        """
        checks if user is member of group_id or role
        """

        group_id = group_id or self.id_group(role)
        try:
            group_id = int(group_id)
        except:
            group_id = self.id_group(group_id)  # interpret group_id as a role
        if not user_id and self.user:
            user_id = self.user.id
        if group_id and user_id and self.db(
           (self.table_membership.user_id == user_id) &
           (self.table_membership.group_id == group_id)).select():
            r = True
        else:
            r = False
        self.log_event(self.messages['has_membership_log'],
                       dict(user_id=user_id, group_id=group_id, check=r))
        return r

    def add_membership(self, group_id=None, user_id=None, role=None):
        """
        gives user_id membership of group_id or role
        if user is None than user_id is that of current logged in user
        """

        group_id = group_id or self.id_group(role)
        try:
            group_id = int(group_id)
        except:
            group_id = self.id_group(group_id)  # interpret group_id as a role
        if not user_id and self.user:
            user_id = self.user.id
        record = self.table_membership(user_id=user_id, group_id=group_id)
        if record:
            return record.id
        else:
            id = self.table_membership.insert(group_id=group_id,
                                              user_id=user_id)
        self.update_groups()
        self.log_event(self.messages['add_membership_log'],
                       dict(user_id=user_id, group_id=group_id))
        return id

    def del_membership(self, group_id=None, user_id=None, role=None):
        """
        revokes membership from group_id to user_id
        if user_id is None than user_id is that of current logged in user
        """

        group_id = group_id or self.id_group(role)
        if not user_id and self.user:
            user_id = self.user.id
        self.log_event(self.messages['del_membership_log'],
                       dict(user_id=user_id, group_id=group_id))
        ret = self.db(self.table_membership.user_id
                      == user_id)(self.table_membership.group_id
                                  == group_id).delete()
        self.update_groups()
        return ret

    def has_permission(self, name='any', table_name='', record_id=0,
                       user_id=None, group_id=None):
        """
        checks if user_id or current logged in user is member of a group
        that has 'name' permission on 'table_name' and 'record_id'
        if group_id is passed, it checks whether the group has the permission
        """

        if not group_id and self.settings.everybody_group_id and \
            self.has_permission(
                name, table_name, record_id, user_id=None,
                group_id=self.settings.everybody_group_id):
                    return True

        if not user_id and not group_id and self.user:
            user_id = self.user.id
        if user_id:
            rows = self.db(self.table_membership.user_id == user_id).select(
                self.table_membership.group_id)
            groups = set([row.group_id for row in rows])
            if group_id and not group_id in groups:
                return False
        else:
            groups = set([group_id])
        rows = self.db(self.table_permission.name == name)(
            self.table_permission.table_name == str(table_name))(
            self.table_permission.record_id == record_id).select(
            self.table_permission.group_id)
        groups_required = set([row.group_id for row in rows])
        if record_id:
            rows = self.db(self.table_permission.name == name)(
                self.table_permission.table_name == str(table_name))(
                self.table_permission.record_id == 0).select(
                self.table_permission.group_id)
            groups_required = groups_required.union(set(
                [row.group_id for row in rows]))
        if groups.intersection(groups_required):
            r = True
        else:
            r = False
        if user_id:
            self.log_event(self.messages['has_permission_log'],
                           dict(user_id=user_id, name=name,
                                table_name=table_name, record_id=record_id))
        return r

    def add_permission(self, group_id, name='any', table_name='', record_id=0):
        """
        gives group_id 'name' access to 'table_name' and 'record_id'
        """

        if group_id == 0:
            group_id = self.user_group()
        record = self.db(self.table_permission.group_id == group_id)(
            self.table_permission.name == name)(
            self.table_permission.table_name == str(table_name))(
            self.table_permission.record_id == long(record_id)).select(
            limitby=(0, 1), orderby_on_limitby=False).first()
        if record:
            id = record.id
        else:
            id = self.table_permission.insert(
                group_id=group_id, name=name, table_name=str(table_name),
                record_id=long(record_id))
        self.log_event(self.messages['add_permission_log'],
                       dict(permission_id=id, group_id=group_id,
                            name=name, table_name=table_name,
                            record_id=record_id))
        return id

    def del_permission(self, group_id, name='any', table_name='', record_id=0):
        """
        revokes group_id 'name' access to 'table_name' and 'record_id'
        """

        self.log_event(
            self.messages['del_permission_log'],
            dict(group_id=group_id, name=name, table_name=table_name,
                 record_id=record_id))
        return self.db(self.table_permission.group_id == group_id)(
            self.table_permission.name == name)(
            self.table_permission.table_name == str(table_name))(
            self.table_permission.record_id == long(record_id)).delete()

    def accessible_query(self, name, table, user_id=None):
        """
        returns a query with all accessible records for user_id or
        the current logged in user
        this method does not work on GAE because uses JOIN and IN

        example:

           db(auth.accessible_query('read', db.mytable)).select(db.mytable.ALL)

        """
        if not user_id:
            user_id = self.user_id
        db = self.db
        if isinstance(table, str) and table in self.db.tables():
            table = self.db[table]
        elif isinstance(table, (Set, Query)):
            # experimental: build a chained query for all tables
            if isinstance(table, Set):
                cquery = table.query
            else:
                cquery = table
            tablenames = db._adapter.tables(cquery)
            for tablename in tablenames:
                cquery &= self.accessible_query(name, tablename,
                                                user_id=user_id)
            return cquery
        if not isinstance(table, str) and\
                self.has_permission(name, table, 0, user_id):
            return table.id > 0
        query = table.id.belongs(db(self.table_membership.user_id == user_id)(
            self.table_membership.group_id == self.table_permission.group_id)(
            self.table_permission.name == name)(
            self.table_permission.table_name == table)._select(
            self.table_permission.record_id))
        if self.settings.everybody_group_id:
            query |= table.id.belongs(db(self.table_permission.group_id ==
                                         self.settings.everybody_group_id)(
                self.table_permission.name == name)(
                self.table_permission.table_name == table)._select(
                self.table_permission.record_id))
        return query

    @staticmethod
    def archive(form, archive_table=None, current_record='current_record',
                archive_current=False, fields=None):
        """
        If you have a table (db.mytable) that needs full revision history you can just do:

            form=crud.update(db.mytable,myrecord,onaccept=auth.archive)

        or

            form=SQLFORM(db.mytable,myrecord).process(onaccept=auth.archive)

        crud.archive will define a new table "mytable_archive" and store
        a copy of the current record (if archive_current=True)
        or a copy of the previous record (if archive_current=False)
        in the newly created table including a reference
        to the current record.

        fields allows to specify extra fields that need to be archived.

        If you want to access such table you need to define it yourself
        in a model:

            db.define_table('mytable_archive',
                Field('current_record',db.mytable),
                db.mytable)

        Notice such table includes all fields of db.mytable plus one: current_record.
        crud.archive does not timestamp the stored record unless your original table
        has a fields like:

            db.define_table(...,
                Field('saved_on','datetime',
                     default=request.now,update=request.now,writable=False),
                Field('saved_by',auth.user,
                     default=auth.user_id,update=auth.user_id,writable=False),

        there is nothing special about these fields since they are filled before
        the record is archived.

        If you want to change the archive table name and the name of the reference field
        you can do, for example:

            db.define_table('myhistory',
                Field('parent_record',db.mytable),
                db.mytable)

        and use it as:

            form=crud.update(db.mytable,myrecord,
                             onaccept=lambda form:crud.archive(form,
                             archive_table=db.myhistory,
                             current_record='parent_record'))

        """
        if not archive_current and not form.record:
            return None
        table = form.table
        if not archive_table:
            archive_table_name = '%s_archive' % table
            if not archive_table_name in table._db:
                table._db.define_table(
                    archive_table_name,
                    Field(current_record, table),
                    *[field.clone(unique=False) for field in table])
            archive_table = table._db[archive_table_name]
        new_record = {current_record: form.vars.id}
        for fieldname in archive_table.fields:
            if not fieldname in ['id', current_record]:
                if archive_current and fieldname in form.vars:
                    new_record[fieldname] = form.vars[fieldname]
                elif form.record and fieldname in form.record:
                    new_record[fieldname] = form.record[fieldname]
        if fields:
            new_record.update(fields)
        id = archive_table.insert(**new_record)
        return id


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
        self.passfield = self.auth.settings.password_field

    def get_user(self):
        return self.user

    def onaccept(self, form):
        userfield = self.userfield
        passfield = self.passfield
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
            elif not temp_user.registration_key is None and \
                    temp_user.registration_key.strip():
                flash(self.auth.messages.registration_verifying)
                return
            #: verify password
            if form.vars.get(passfield, '') == temp_user[passfield]:
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
        from ..validators import isEmail, isntEmpty, Lower
        userfield = self.userfield
        passfield = self.passfield
        if userfield == 'email':
            tmpvalidator = isEmail(
                error_message=self.auth.messages.invalid_email)
            if not self.auth.settings.email_case_sensitive:
                tmpvalidator = [Lower(), tmpvalidator]
        else:
            tmpvalidator = isntEmpty(
                error_message=self.auth.messages.is_empty)
            if not self.auth.settings.username_case_sensitive:
                tmpvalidator = [Lower(), tmpvalidator]
        form_fields = [self.auth.table_user[userfield].clone(),
                       self.auth.table_user[passfield]]
        form_fields[0].requires = tmpvalidator
        if self.auth.settings.remember_me_form:
            form_fields.append(Field(
                'remember',
                'boolean',
                default=True,
                label=T('Remember me')))
        form = Form(
            *form_fields,
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


def callback(actions, form, tablename=None):
    if actions:
        if tablename and isinstance(actions, dict):
            actions = actions.get(tablename, [])
        if not isinstance(actions, (list, tuple)):
            actions = [actions]
        [action(form) for action in actions]


def call_or_redirect(f, *args):
    if callable(f):
        redirect(f(*args))
    else:
        redirect(f)


def replace_id(u, form):
    if u:
        u = u.replace('[id]', str(form.vars.id))
        if u[0] == '/' or u[:4] == 'http':
            return u
    return '/account'+u


class AuthManager(Handler):
    def __init__(self, auth):
        #: the Auth() instance
        self.auth = auth

    def on_start(self):
        # check auth session is valid
        if self.auth._auth and self.auth._auth.last_visit and \
           self.auth._auth.last_visit + \
           timedelta(days=0, seconds=self.auth._auth.expiration) > request.now:
            # this is a trick to speed up sessions
            if (request.now - self.auth._auth.last_visit).seconds > \
               (self.auth._auth.expiration / 10):
                self.auth._auth.last_visit = request.now
        else:
            # if auth session is not valid and existent, delete it
            if self.auth._auth:
                del session.auth

    def on_success(self):
        # set correct session expiration if requested by user
        if self.auth._auth and self.auth._auth.remember:
            session._expires_after(self.auth._auth.expiration)

    def on_failure(self):
        # run on_success to keep session state on errors
        self.on_success()


class ModelsAuth(Auth):
    def __init__(self, app, db, usermodel, **kwargs):
        # init auth without defining tables
        kwargs['define_tables'] = False
        Auth.__init__(self, app, db, **kwargs)
        # load the user Model
        _use_signature = kwargs.get('use_signature')
        _migrate = kwargs.get('migrate')
        _fake_migrate = kwargs.get('fake_migrate')
        usermodel.auth = self
        usermodel.db = self.db
        user = usermodel(_migrate, _fake_migrate, _use_signature)
        user.entity = self.table_user
        # load user's definitions
        getattr(user, '_AuthModel__define')()
        # set reference in db for datamodel name
        setattr(db, usermodel.__name__, user.entity)
        self.entity = user.entity
        if app.config.get('auth', {}).get('server', 'default') != "default":
            self.settings.mailer.server = app.config.auth.server
            self.settings.mailer.sender = app.config.auth.sender
            self.settings.mailer.login = app.config.auth.login
