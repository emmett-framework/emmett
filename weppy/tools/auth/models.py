# -*- coding: utf-8 -*-
"""
    weppy.tools.auth.models
    -----------------------

    Provides models for the authorization system.

    :copyright: (c) 2015 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

from datetime import datetime
from ...dal import Model, Field, before_insert
from ...globals import current, request
from ...security import uuid


def _now():
    if hasattr(current, 'request'):
        return request.now
    return datetime.utcnow()


class TimestampedModel(Model):
    created_at = Field('datetime', default=_now, rw=False)
    updated_at = Field('datetime', default=_now, update=_now, rw=False)


class AuthModel(Model):
    auth = None

    form_registration_rw = {}
    form_profile_rw = {}

    def __super_method(self, name):
        return getattr(super(AuthModel, self), '_Model__'+name)

    def _define_(self):
        self.__super_method('define_validation')()
        self.__super_method('define_defaults')()
        self.__super_method('define_updates')()
        self.__super_method('define_representation')()
        self.__super_method('define_computations')()
        self.__super_method('define_actions')()
        self.__hide_all()
        self.__super_method('define_form_utils')
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
        return [field.name for field in self.table
                if field.type != 'id' and field.writable]

    def __define_authform_utils(self):
        settings_map = {
            'register_fields': 'form_registration_rw',
            'profile_fields': 'form_profile_rw'
        }
        for setting, attr in settings_map.items():
            l = self.auth.settings[setting] or self.__base_visibility()
            for field, value in getattr(self, attr).items():
                show = value[1] if isinstance(value, (tuple, list)) else value
                if show:
                    #self.table[field].writable = value[0]
                    #self.table[field].readable = value[1]
                    l.append(field)
                else:
                    if field in l:
                        l.remove(field)
            if l:
                self.auth.settings[setting] = l


class AuthUserBasic(AuthModel, TimestampedModel):
    format = '%(email)s (%(id)s)'
    #: injected by Auth
    #  has_many(
    #      {'memberships': 'AuthMembership'},
    #      {'authevents': 'AuthEvent'},
    #      {'authgroups': {'via': 'memberships'}},
    #      {'permissions': {'via': 'authgroups'}},
    #  )

    email = Field(length=512, unique=True)
    password = Field('password', length=512)
    registration_key = Field(length=512, rw=False, default='')
    reset_password_key = Field(length=512, rw=False, default='')
    registration_id = Field(length=512, rw=False, default='')

    form_labels = {
        'email': 'E-mail',
        'password': 'Password'
    }

    @before_insert
    def set_registration_key(self, fields):
        if self.auth.settings.registration_requires_verification and not \
                fields.get('registration_key'):
            fields['registration_key'] = uuid()


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
    #      {'memberships': 'AuthMembership'},
    #      {'permissions': 'AuthPermission'},
    #      {'users': {'via': 'memberships'}}
    #  )

    role = Field(length=512, default='', unique=True)
    description = Field('text')

    form_labels = {
        'role': 'Role',
        'description': 'Description'
    }


class AuthMembership(TimestampedModel):
    #: injected by Auth
    #  belongs_to({'user': 'AuthUser'}, {'authgroup': 'AuthGroup'})
    pass


class AuthPermission(TimestampedModel):
    #: injected by Auth
    #  belongs_to({'authgroup': 'AuthGroup'})

    name = Field(length=512, default='default', notnull=True)
    table_name = Field(length=512)
    record_id = Field('int', default=0)

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
    description = Field('text', notnull=True)

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


"""
class AuthUserSigned(AuthUser):
    is_active = Field('bool', default=True, rw=False)
    created_on = Field('datetime', default=lambda: datetime.utcnow(), rw=False)
    created_by = Field('reference auth_user', default=auth.user_id, rw=False)
    modified_on = Field('datetime', default=lambda: datetime.utcnow(),
                        update=lambda: datetime.utcnow(), rw=False),
    modified_by = Field('reference auth_user', default=auth.user_id,
                        update=auth.user_id, rw=False)
"""
