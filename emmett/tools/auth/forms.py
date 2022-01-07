# -*- coding: utf-8 -*-
"""
    emmett.tools.auth.forms
    -----------------------

    Provides the forms for the authorization system.

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

from ...forms import Form, ModelForm
from ...orm import Field


class AuthForms(object):
    _registry_ = {}
    _fields_registry_ = {}

    @classmethod
    def register_for(cls, target, fields=lambda: None):
        def wrap(f):
            cls._registry_[target] = f
            cls._fields_registry_[target] = fields
            return f
        return wrap

    @classmethod
    def get_for(cls, target):
        return cls._registry_[target], cls._fields_registry_[target]

    @classmethod
    def map(cls):
        rv = {}
        for key in cls._registry_.keys():
            rv[key] = cls.get_for(key)
        return rv


def login_fields(auth):
    model = auth.models['user']
    rv = {
        'email': Field(
            validation={'is': 'email', 'presence': True},
            label=model.email.label),
        'password': Field(
            'password', validation=model.password._requires,
            label=model.password.label)
    }
    if auth.ext.config.remember_option:
        rv['remember'] = Field(
            'bool', default=True,
            label=auth.ext.config.messages['remember_button'])
    return rv


def registration_fields(auth):
    rw_data = auth.models['user']._instance_()._merged_form_rw_
    user_table = auth.models['user'].table
    all_fields = [
        (field_name, user_table[field_name].clone())
        for field_name in rw_data['registration']['writable']
    ]
    for i, (field_name, field) in enumerate(all_fields):
        if field_name == 'password':
            all_fields.insert(
                i + 1, (
                    'password2',
                    Field(
                        'password',
                        label=auth.ext.config.messages['verify_password'])))
            break
    rv = {}
    for i, (field_name, field) in enumerate(all_fields):
        field.writable = True
        rv[field_name] = field
        rv[field_name]._inst_count_ = i
    return rv


def profile_fields(auth):
    rw_data = auth.models['user']._instance_()._merged_form_rw_
    return rw_data['profile']


def password_retrieval_fields(auth):
    rv = {
        'email': Field(
            validation={'is': 'email', 'presence': True, 'lower': True}),
    }
    return rv


def password_reset_fields(auth):
    password_field = auth.ext.config.models['user'].password
    rv = {
        'password': Field(
            'password', validation=password_field._requires,
            label=auth.ext.config.messages['new_password']),
        'password2': Field(
            'password', label=auth.ext.config.messages['verify_password'])
    }
    return rv


def password_change_fields(auth):
    password_validation = auth.ext.config.models['user'].password._requires
    rv = {
        'old_password': Field(
            'password', validation=password_validation,
            label=auth.ext.config.messages['old_password']),
        'new_password': Field(
            'password', validation=password_validation,
            label=auth.ext.config.messages['new_password']),
        'new_password2': Field(
            'password', label=auth.ext.config.messages['verify_password'])
    }
    return rv


@AuthForms.register_for('login', fields=login_fields)
def login_form(auth, fields, **kwargs):
    opts = {
        'submit': auth.ext.config.messages['login_button'], 'keepvalues': True}
    opts.update(**kwargs)
    return Form(
        fields,
        **opts
    )


@AuthForms.register_for('registration', fields=registration_fields)
def registration_form(auth, fields, **kwargs):
    opts = {
        'submit': auth.ext.config.messages['registration_button'],
        'keepvalues': True}
    opts.update(**kwargs)
    return Form(
        fields,
        **opts
    )


@AuthForms.register_for('profile', fields=profile_fields)
def profile_form(auth, fields, **kwargs):
    opts = {
        'submit': auth.ext.config.messages['profile_button'],
        'keepvalues': True}
    opts.update(**kwargs)
    return ModelForm(
        auth.models['user'],
        record_id=auth.user.id,
        fields=fields,
        upload=auth.ext.exposer.url('download'),
        **opts
    )


@AuthForms.register_for('password_retrieval', fields=password_retrieval_fields)
def password_retrieval_form(auth, fields, **kwargs):
    opts = {'submit': auth.ext.config.messages['password_retrieval_button']}
    opts.update(**kwargs)
    return Form(
        fields,
        **opts
    )


@AuthForms.register_for('password_reset', fields=password_reset_fields)
def password_reset_form(auth, fields, **kwargs):
    opts = {
        'submit': auth.ext.config.messages['password_reset_button'],
        'keepvalues': True}
    opts.update(**kwargs)
    return Form(
        fields,
        **opts
    )


@AuthForms.register_for('password_change', fields=password_change_fields)
def password_change_form(auth, fields, **kwargs):
    opts = {
        'submit': auth.ext.config.messages['password_change_button'],
        'keepvalues': True}
    opts.update(**kwargs)
    return Form(
        fields,
        **opts
    )
