import urllib
from pydal.objects import Row, Set, Query
from ...datastructures import sdict
from ...globals import request, session
from ...http import HTTP, redirect
from ...security import uuid
from ..mail import Mail
from .defaults import default_settings, default_messages
from .exposer import Exposer
from .handlers import AuthManager, AuthLoginHandler
from .helpers import get_vars_next
from .models import AuthModel


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
        #TEMP
        self.app = app
        #
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
            on_failed_authorization=url_index+"/not_authorized",
            login_next=url_index+"/profile",
            login_methods=[self],
            login_form=self,
            logout_next=url_index,
            register_next=url_index,
            verify_email_next=url_login,
            profile_next=url_index,
            retrieve_username_next=url_index,
            retrieve_password_next=url_index,
            request_reset_password_next=url_login,
            reset_password_next=url_index,
            change_password_next=url_index,
            hmac_key=hmac_key
        )
        #: load user's settings
        for key, value in app.config.auth.items():
            if key in self.settings.keys():
                self.settings[key] = value

        #: load messages
        messages = self.messages = sdict()
        messages.update(default_messages)
        messages.update(self.settings.messages)

        #if signature:
        #    self.define_signature()
        #else:
        #    self.signature = None

        _use_signature = kwargs.get('sign_tables')

        self._usermodel = None
        if usermodel:
            if not issubclass(usermodel, AuthModel):
                raise RuntimeError('%s is an invalid user model' %
                                   usermodel.__name__)
            self.settings.models.user = usermodel
        #if usermodel:
        #    from ..dal import AuthModel
        #    if not issubclass(usermodel, AuthModel):
        #        raise RuntimeError('%s is an invalid user model' %
        #                           usermodel.__name__)
        #    self._init_usermodel(usermodel, _use_signature)
        #else:
        #    self.define_tables(_use_signature)
        self.define_models()
        self.exposer = Exposer(self)

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
                self.register_action(k, getattr(self.exposer, k))

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

    @property
    def user_id(self):
        return self.user and self.user.id or None

    @property
    def table_user(self):
        return self.db[self._model_names.user]

    @property
    def table_group(self):
        return self.db[self._model_names.group]

    @property
    def table_membership(self):
        return self.db[self._model_names.membership]

    @property
    def table_permission(self):
        return self.db[self._model_names.permission]

    @property
    def table_event(self):
        return self.db[self._model_names.event]

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
        #elif f in self.settings.actions_disabled:
        #    raise HTTP(404)
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

    def define_models(self):
        def get_modelnames():
            rv = {}
            def_names = {
                'user': 'user',
                'group': 'authgroup',
                'membership': 'membership',
                'permission': 'permission',
                'event': 'authevent'
            }
            for m in ['user', 'group', 'membership', 'permission', 'event']:
                if self.settings.models[m] == default_settings.models[m]:
                    rv[m] = def_names[m]
                else:
                    rv[m] = self.settings.models[m].__name__.lower()
            return rv

        names = get_modelnames()
        models = self.settings.models
        #: AuthUser
        user_model = models['user']
        #model_format = '%(first_name)s %(last_name)s (%(id)s)'
        #if not self.settings.user_firstname_lastname:
        #    delattr(user_model, 'first_name')
        #    delattr(user_model, 'last_name')
        #    del user_model.form_labels['first_name']
        #    del user_model.form_labels['last_name']
        #    model_format = '%(email)s (%(id)s)'
        #if not hasattr(user_model, 'format'):
        #    setattr(user_model, 'format', model_format)
        many_refs = [
            {names['membership']+'s': models['membership'].__name__},
            {names['event']+'s': models['event'].__name__},
            {names['group']+'s': {'via': names['membership']+'s'}},
            {names['permission']+'s': {'via': names['group']+'s'}}
        ]
        if getattr(user_model, '_auto_relations', True):
            user_model._hasmany_ref_ = many_refs
        #: AuthGroup
        group_model = models['group']
        if not hasattr(group_model, 'format'):
            setattr(group_model, 'format', '%(role)s (%(id)s)')
        #if not group_model.form_labels:
        #    setattr(group_model, 'form_labels', labels)
        many_refs = [
            {names['membership']+'s': models['membership'].__name__},
            {names['permission']+'s': models['permission'].__name__},
            {names['user']+'s': {'via': names['membership']+'s'}}
        ]
        if getattr(group_model, '_auto_relations', True):
            group_model._hasmany_ref_ = many_refs
        #: AuthMembership
        membership_model = models['membership']
        belongs_refs = [
            {names['user']: models['user'].__name__},
            {names['group']: models['group'].__name__}
        ]
        if getattr(membership_model, '_auto_relations', True):
            membership_model._belongs_ref_ = belongs_refs
        #: AuthPermission
        permission_model = models['permission']
        belongs_refs = [
            {names['group']: models['group'].__name__}
        ]
        if getattr(permission_model, '_auto_relations', True):
            permission_model._belongs_ref_ = belongs_refs
        #: AuthEvent
        event_model = models['event']
        belongs_refs = [
            {names['user']: models['user'].__name__}
        ]
        if getattr(event_model, '_auto_relations', True):
            event_model._belongs_ref_ = belongs_refs
        # SIGNATURE?
        models.user.auth = self
        self.db.define_models(
            models.user, models.group, models.membership, models.permission,
            models.event
        )
        self._model_names = sdict()
        for key, value in models.iteritems():
            self._model_names[key] = value.__name__

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
            origin=origin, user=user_id)

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
        if 'registration_id' not in keys:
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
            if 'first_name' not in keys and 'first_name' in \
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
        #self.update_groups()

    def _get_login_settings(self):
        userfield = self.settings.login_userfield or 'username' \
            if 'username' in self.table_user.fields else 'email'
        passfield = self.settings.password_field
        return sdict(table_user=self.table_user, userfield=userfield,
                     passfield=passfield)

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
        snext = get_vars_next()
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

    def is_logged_in(self):
        """
        checks if the user is logged in and returns True/False.
        if so user is in auth.user as well as in session.auth.user
        """

        if self.user:
            return True
        return False

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

    def run_login_onaccept(self):
        onaccept = self.settings.login_onaccept
        if onaccept:
            form = sdict(dict(vars=self.user))
            if not isinstance(onaccept, (list, tuple)):
                onaccept = [onaccept]
            for callback in onaccept:
                callback(form)

    """
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
    """

    def add_group(self, role, description=''):
        """
        creates a group associated to a role
        """

        group_id = self.table_group.insert(
            role=role, description=description)
        self.log_event(self.messages['add_group_log'],
                       dict(authgroup=group_id, role=role))
        return group_id

    def del_group(self, group_id):
        """
        deletes a group
        """
        self.db(self.table_group.id == group_id).delete()
        self.db(self.table_membership.group_id == group_id).delete()
        self.db(self.table_permission.group_id == group_id).delete()
        #self.update_groups()
        self.log_event(self.messages.del_group_log, dict(authgroup=group_id))

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
                       dict(user=user_id, authgroup=group_id, check=r))
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
        #self.update_groups()
        self.log_event(self.messages['add_membership_log'],
                       dict(user=user_id, authgroup=group_id))
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
                       dict(user=user_id, authgroup=group_id))
        ret = self.db(self.table_membership.user_id
                      == user_id)(self.table_membership.group_id
                                  == group_id).delete()
        #self.update_groups()
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
            if group_id and group_id not in groups:
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
                           dict(user=user_id, name=name,
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
                       dict(permission_id=id, authgroup=group_id,
                            name=name, table_name=table_name,
                            record_id=record_id))
        return id

    def del_permission(self, group_id, name='any', table_name='', record_id=0):
        """
        revokes group_id 'name' access to 'table_name' and 'record_id'
        """

        self.log_event(
            self.messages['del_permission_log'],
            dict(authgroup=group_id, name=name, table_name=table_name,
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

    """
    @staticmethod
    def archive(form, archive_table=None, current_record='current_record',
                archive_current=False, fields=None):
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
    """
