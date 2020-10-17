# -*- coding: utf-8 -*-
"""
    emmett.tools.auth.models
    ------------------------

    Provides models for the authorization system.

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

from ...ctx import current
from ...locals import now, request
from ...orm import Model, Field, before_insert, rowmethod
from ...security import uuid


class TimestampedModel(Model):
    created_at = Field.datetime(default=now, rw=False)
    updated_at = Field.datetime(default=now, update=now, rw=False)


class AuthModel(Model):
    _additional_inheritable_dict_attrs_ = [
        'form_registration_rw', 'form_profile_rw']
    auth = None

    @classmethod
    def _init_inheritable_dicts_(cls):
        for attr in cls._additional_inheritable_dict_attrs_:
            if isinstance(attr, tuple):
                attr_name, default = attr
            else:
                attr_name, default = attr, {}
            if not isinstance(default, dict):
                raise SyntaxError(
                    "{} is not a dictionary".format(attr_name))
            setattr(cls, attr_name, default)

    @classmethod
    def _merge_inheritable_dicts_(cls, models):
        super(AuthModel, cls)._merge_inheritable_dicts_(models)
        for attr in cls._additional_inheritable_dict_attrs_:
            if isinstance(attr, tuple):
                attr_name = attr[0]
            else:
                attr_name = attr
            attrs = {}
            for model in models:
                if not issubclass(model, AuthModel):
                    continue
                superattrs = getattr(model, attr_name)
                for k, v in superattrs.items():
                    attrs[k] = v
            for k, v in getattr(cls, attr_name).items():
                attrs[k] = v
            setattr(cls, attr_name, attrs)

    def __super_method(self, name):
        return getattr(super(AuthModel, self), '_Model__' + name)

    def _define_(self):
        self.__hide_all()
        self.__super_method('define_indexes')()
        self.__super_method('define_validation')()
        self.__super_method('define_access')()
        self.__super_method('define_defaults')()
        self.__super_method('define_updates')()
        self.__super_method('define_representation')()
        self.__super_method('define_computations')()
        self.__super_method('define_callbacks')()
        self.__super_method('define_scopes')()
        self.__super_method('define_form_utils')()
        self.__define_authform_utils()
        self.setup()

    #def __define_extra_fields(self):
    #    self.auth.settings.extra_fields['auth_user'] = self.fields

    def __hide_all(self):
        alwaysvisible = ['first_name', 'last_name', 'password', 'email']
        for field in self.table.fields:
            if field not in alwaysvisible:
                self.table[field].writable = self.table[field].readable = \
                    False

    def __base_visibility(self):
        rv = {}
        for field in self.table:
            rv[field.name] = field.readable, field.writable
        return rv

    def __define_authform_utils(self):
        settings = {
            'form_registration_rw': {'writable': [], 'readable': []},
            'form_profile_rw': {'writable': [], 'readable': []}}
        for config_dict in settings.keys():
            rw_data = self.__base_visibility()
            rw_data.update(**self.fields_rw)
            rw_data.update(**getattr(self, config_dict))
            for key, value in rw_data.items():
                if isinstance(value, (tuple, list)):
                    readable, writable = value
                else:
                    readable = writable = value
                if readable:
                    settings[config_dict]['readable'].append(key)
                if writable:
                    settings[config_dict]['writable'].append(key)
        setattr(self, '_merged_form_rw_', {
            'registration': settings['form_registration_rw'],
            'profile': settings['form_profile_rw']})


class AuthUserBasic(AuthModel, TimestampedModel):
    tablename = "auth_users"
    format = '%(email)s (%(id)s)'
    #: injected by Auth
    #  has_many(
    #      {'auth_memberships': 'AuthMembership'},
    #      {'auth_events': 'AuthEvent'},
    #      {'auth_groups': {'via': 'auth_memberships'}},
    #      {'auth_permissions': {'via': 'auth_groups'}},
    #  )

    email = Field(length=255, unique=True)
    password = Field.password(length=512)
    registration_key = Field(length=512, rw=False, default='')
    reset_password_key = Field(length=512, rw=False, default='')
    registration_id = Field(length=512, rw=False, default='')

    form_labels = {
        'email': 'E-mail',
        'password': 'Password'
    }

    form_profile_rw = {
        'email': (True, False),
        'password': False
    }

    @before_insert
    def set_registration_key(self, fields):
        if self.auth.config.registration_verification and not \
                fields.get('registration_key'):
            fields['registration_key'] = uuid()
        elif self.auth.config.registration_approval:
            fields['registration_key'] = 'pending'

    @rowmethod('disable')
    def _set_disabled(self, row):
        return row.update_record(registration_key='disabled')

    @rowmethod('block')
    def _set_blocked(self, row):
        return row.update_record(registration_key='blocked')

    @rowmethod('allow')
    def _set_allowed(self, row):
        return row.update_record(registration_key='')


class AuthUser(AuthUserBasic):
    format = '%(first_name)s %(last_name)s (%(id)s)'

    first_name = Field(length=128, notnull=True)
    last_name = Field(length=128, notnull=True)

    form_labels = {
        'first_name': 'First name',
        'last_name': 'Last name',
    }


class AuthGroup(TimestampedModel):
    format = '%(role)s (%(id)s)'
    #: injected by Auth
    #  has_many(
    #      {'auth_memberships': 'AuthMembership'},
    #      {'auth_permissions': 'AuthPermission'},
    #      {'users': {'via': 'memberships'}}
    #  )

    role = Field(length=255, default='', unique=True)
    description = Field.text()

    form_labels = {
        'role': 'Role',
        'description': 'Description'
    }


class AuthMembership(TimestampedModel):
    #: injected by Auth
    #  belongs_to({'user': 'AuthUser'}, {'auth_group': 'AuthGroup'})
    pass


class AuthPermission(TimestampedModel):
    #: injected by Auth
    #  belongs_to({'auth_group': 'AuthGroup'})

    name = Field(length=512, default='default', notnull=True)
    table_name = Field(length=512)
    record_id = Field.int(default=0)

    validation = {
        'record_id': {'in': {'range': (0, 10**9)}}
    }

    form_labels = {
        'name': 'Name',
        'table_name': 'Object or table name',
        'record_id': 'Record ID'
    }


class AuthEvent(TimestampedModel):
    #: injected by Auth
    #  belongs_to({'user': 'AuthUser'})

    client_ip = Field()
    origin = Field(length=512, notnull=True)
    description = Field.text(notnull=True)

    default_values = {
        'client_ip': lambda:
            request.client if hasattr(current, 'request') else 'unavailable',
        'origin': 'auth',
        'description': ''
    }

    #: labels injected by Auth
    form_labels = {
        'client_ip': 'Client IP',
        'origin': 'Origin',
        'description': 'Description'
    }
