# -*- coding: utf-8 -*-
"""
emmett.tools.auth.ext
---------------------

Provides the main auth layer.

:copyright: 2014 Giovanni Barillari
:license: BSD-3-Clause
"""

import time
from functools import wraps

import click

from ..._shortcuts import uuid
from ...cli import pass_script_info
from ...datastructures import sdict
from ...extensions import Extension, Signals, listen_signal
from ...language.helpers import Tstr
from ...locals import T, now, session
from ...orm.helpers import decamelize
from .forms import AuthForms
from .models import AuthEvent, AuthGroup, AuthMembership, AuthModel, AuthPermission, AuthUser


class AuthExtension(Extension):
    namespace = "auth"

    default_config = {
        "models": {
            "user": AuthUser,
            "group": AuthGroup,
            "membership": AuthMembership,
            "permission": AuthPermission,
            "event": AuthEvent,
        },
        "hmac_key": None,
        "hmac_alg": "pbkdf2(2000,20,sha512)",
        "inject_pipe": False,
        "log_events": True,
        "flash_messages": True,
        "csrf": True,
        "enabled_routes": [
            "login",
            "logout",
            "registration",
            "profile",
            "email_verification",
            "password_retrieval",
            "password_reset",
            "password_change",
            "download",
        ],
        "disabled_routes": [],
        "routes_paths": {
            "login": "/login",
            "logout": "/logout",
            "registration": "/registration",
            "profile": "/profile",
            "email_verification": "/email_verification/<str:key>",
            "password_retrieval": "/password_retrieval",
            "password_reset": "/password_reset/<str:key>",
            "password_change": "/password_change",
            "download": "/download/<str:file_name>",
        },
        "single_template": False,
        "password_min_length": 6,
        "remember_option": True,
        "session_expiration": 3600,
        "session_long_expiration": 3600 * 24 * 30,
        "registration_verification": True,
        "registration_approval": False,
    }
    default_messages = {
        "approval_pending": "Registration is pending approval",
        "verification_pending": "Registration needs verification",
        "login_disabled": "The account is locked",
        "login_invalid": "Invalid credentials",
        "logged_out": "Logged out successfully",
        "registration_success": "Registration completed",
        "profile_updated": "Profile updated successfully",
        "verification_success": "Account verification completed",
        "password_changed": "Password changed successfully",
        "mail_failure": "Something went wrong with the email, try again later",
        "mail_success": "We sent you an email, check your inbox",
        "reset_key_invalid": "The reset link was invalid or expired",
        "login_button": "Sign in",
        "registration_button": "Register",
        "profile_button": "Save",
        "remember_button": "Remember me",
        "password_retrieval_button": "Retrieve password",
        "password_reset_button": "Reset password",
        "password_change_button": "Change password",
        "login_log": "User {id} logged in",
        "logout_log": "User {id} logged out",
        "registration_log": "User {id} registered",
        "profile_log": "User {id} updated profile",
        "email_verification_log": "Verification email sent to user {id}",
        "password_retrieval_log": "User {id} asked for password retrieval",
        "password_reset_log": "User {id} reset the password",
        "password_change_log": "User {id} changed the password",
        "old_password": "Current password",
        "new_password": "New password",
        "verify_password": "Confirm password",
        "registration_email_subject": "Email verification",
        "registration_email_text": "Hello {email}! Click on the link {link} to verify your email",
        "reset_password_email_subject": "Password reset requested",
        "reset_password_email_text": "A password reset was requested for your account, "
        "click on the link {link} to proceed",
    }

    def __init__(self, app, env, config):
        super(AuthExtension, self).__init__(app, env, config)
        self.__init_messages()
        self.__init_mails()
        AuthModel._init_inheritable_dicts_()
        AuthModel.auth = self

    def __init_messages(self):
        self.config.messages = self.config.get("messages", sdict())
        for key, dval in self.default_messages.items():
            self.config.messages[key] = T(self.config.messages.get(key, dval))

    def __init_mails(self):
        self.mails = {"registration": self._registration_email, "reset_password": self._reset_password_email}

    def __register_commands(self):
        @self.app.cli.group("auth", short_help="Auth commands")
        def cli_group():
            pass

        @cli_group.command("generate_key", short_help="Generate an auth key")
        @pass_script_info
        def generate_key(info):
            click.echo(uuid())

    def __ensure_config(self):
        for key in set(self.default_config["routes_paths"].keys()) - set(self.config["routes_paths"].keys()):
            self.config["routes_paths"][key] = self.default_config["routes_paths"][key]

    def __get_relnames(self):
        rv = {}
        def_names = {
            "user": "user",
            "group": "auth_group",
            "membership": "auth_membership",
            "permission": "auth_permission",
            "event": "auth_event",
        }
        for m in ["user", "group", "membership", "permission", "event"]:
            if self.config.models[m] == self.default_config["models"][m]:
                rv[m] = def_names[m]
            else:
                rv[m] = decamelize(self.config.models[m].__name__)
        return rv

    def on_load(self):
        self.__register_commands()
        if self.config.hmac_key is None:
            self.app.log.warn(
                "An auto-generated 'hmac_key' was added to the auth "
                "configuration.\nPlase add your own key to the configuration. "
                "You can generate a key using the auth command.\n"
                "> emmett -a {your_app_name} auth generate_key"
            )
            self.config.hmac_key = uuid()
        self._hmac_key = self.config.hmac_alg + ":" + self.config.hmac_key
        if "MailExtension" not in self.app.ext:
            self.app.log.warn("No mailer seems to be configured. The auth features " "requiring mailer won't work.")
        self.__ensure_config()
        self.relation_names = self.__get_relnames()

    def bind_auth(self, auth):
        self.auth = auth

    def bind_exposer(self, exposer):
        self.exposer = exposer

    @listen_signal(Signals.before_routes)
    def _inject_pipe(self):
        if self.config.inject_pipe:
            self.app.pipeline.append(self.auth.pipe)

    def __set_model_for_key(self, key, model):
        if not model:
            return
        _model_bases = {
            "user": AuthModel,
            "group": AuthGroup,
            "membership": AuthMembership,
            "permission": AuthPermission,
        }
        if not issubclass(model, _model_bases[key]):
            raise RuntimeError(f"{model.__name__} is an invalid {key} auth model")
        self.config.models[key] = model

    def use_database(self, db, user_model=None, group_model=None, membership_model=None, permission_model=None):
        self.db = db
        self.__set_model_for_key("user", user_model)
        self.__set_model_for_key("group", group_model)
        self.__set_model_for_key("membership", membership_model)
        self.__set_model_for_key("permission", permission_model)
        self.define_models()

    def __set_models_labels(self):
        for model in self.default_config["models"].values():
            for supmodel in list(reversed(model.__mro__))[1:]:
                if not supmodel.__module__.startswith("emmett.tools.auth.models"):
                    continue
                if not hasattr(supmodel, "form_labels"):
                    continue
                current_labels = {}
                for key, val in supmodel.form_labels.items():
                    current_labels[key] = T(val)
                supmodel.form_labels = current_labels

    def define_models(self):
        self.__set_models_labels()
        names = self.relation_names
        models = self.config.models
        #: AuthUser
        user_model = models["user"]
        many_refs = [
            {names["membership"] + "s": models["membership"].__name__},
            {names["event"] + "s": models["event"].__name__},
            {names["group"] + "s": {"via": names["membership"] + "s"}},
            {names["permission"] + "s": {"via": names["group"] + "s"}},
        ]
        if getattr(user_model, "_auto_relations", True):
            for el in many_refs:
                key = list(el)[0]
                user_model._all_hasmany_ref_[key] = el
        if user_model.validation.get("password") is None:
            user_model.validation["password"] = {
                "len": {"gte": self.config.password_min_length},
                "crypt": {"key": self._hmac_key},
            }
        #: AuthGroup
        group_model = models["group"]
        if not hasattr(group_model, "format"):
            group_model.format = "%(role)s (%(id)s)"
        many_refs = [
            {names["membership"] + "s": models["membership"].__name__},
            {names["permission"] + "s": models["permission"].__name__},
            {names["user"] + "s": {"via": names["membership"] + "s"}},
        ]
        if getattr(group_model, "_auto_relations", True):
            for el in many_refs:
                key = list(el)[0]
                group_model._all_hasmany_ref_[key] = el
        #: AuthMembership
        membership_model = models["membership"]
        belongs_refs = [{names["user"]: models["user"].__name__}, {names["group"]: models["group"].__name__}]
        if getattr(membership_model, "_auto_relations", True):
            for el in belongs_refs:
                key = list(el)[0]
                membership_model._all_belongs_ref_[key] = el
        #: AuthPermission
        permission_model = models["permission"]
        belongs_refs = [{names["group"]: models["group"].__name__}]
        if getattr(permission_model, "_auto_relations", True):
            for el in belongs_refs:
                key = list(el)[0]
                permission_model._all_belongs_ref_[key] = el
        #: AuthEvent
        event_model = models["event"]
        belongs_refs = [{names["user"]: models["user"].__name__}]
        if getattr(event_model, "_auto_relations", True):
            for el in belongs_refs:
                key = list(el)[0]
                event_model._all_belongs_ref_[key] = el
        self.db.define_models(
            models["user"], models["group"], models["membership"], models["permission"], models["event"]
        )
        self.model_names = sdict()
        for key, value in models.items():
            self.model_names[key] = value.__name__

    def init_forms(self):
        self.forms = sdict()
        for key, (method, fields_method) in AuthForms.map().items():
            self.forms[key] = _wrap_form(method, fields_method(self.auth), self.auth)

    def login_user(self, user, remember=False):
        try:
            del user.password
        except Exception:
            pass
        expiration = remember and self.config.session_long_expiration or self.config.session_expiration
        session.auth = sdict(
            user=user,
            last_visit=now().as_naive_datetime(),
            last_dbcheck=now().as_naive_datetime(),
            expiration=expiration,
            remember=remember,
        )

    def log_event(self, description, data={}, origin="auth", user=None):
        if not self.config.log_events or not description:
            return
        try:
            user_id = user.id if user else self.auth.user.id
        except Exception:
            user_id = None
        # log messages should not be translated
        if isinstance(description, Tstr):
            description = description.text
        self.config.models["event"].table.insert(description=str(description % data), origin=origin, user=user_id)

    def generate_reset_key(self, user):
        key = str(int(time.time())) + "-" + uuid()
        user.update_record(reset_password_key=key)
        return key

    def get_user_by_reset_key(self, key):
        try:
            generated_at = int(key.split("-")[0])
            if time.time() - generated_at > 60 * 60 * 24:
                raise ValueError
            user = self.config.models["user"].get(reset_password_key=key)
        except ValueError:
            user = None
        return user

    def _registration_email(self, user, data):
        data["email"] = user.email
        return self.app.ext.MailExtension.send_mail(
            recipients=user.email,
            subject=str(self.config.messages["registration_email_subject"]),
            body=str(self.config.messages["registration_email_text"] % data),
        )

    def _reset_password_email(self, user, data):
        data["email"] = user.email
        return self.app.ext.MailExtension.send_mail(
            recipients=user.email,
            subject=str(self.config.messages["reset_password_email_subject"]),
            body=str(self.config.messages["reset_password_email_text"] % data),
        )


def _wrap_form(f, fields, auth):
    @wraps(f)
    def wrapped(*args, **kwargs):
        return f(auth, fields, *args, **kwargs)

    return wrapped
