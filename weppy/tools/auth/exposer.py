# -*- coding: utf-8 -*-
"""
    weppy.tools.auth.exposer
    ------------------------

    Provides the exposed functions and logics for the authorization system.

    :copyright: (c) 2015 by Giovanni Barillari

    Based on the web2py's auth module (http://www.web2py.com)
    :copyright: (c) by Massimo Di Pierro <mdipierro@cs.depaul.edu>

    :license: LGPLv3 (http://www.gnu.org/licenses/lgpl.html)
"""

import time
from ...dal import Field
from ...forms import Form, DALForm
from ...globals import request, session
from ...helpers import flash, abort
from ...http import redirect
from .handlers import DefaultLoginHandler
from .helpers import callback, replace_id, get_vars_next


class Exposer(object):
    def __init__(self, auth):
        self.auth = auth
        self.settings = auth.settings
        self.messages = auth.messages
        self.form_data = {}
        self._build_register_form_()
        self._build_retrieve_username_form_()
        self._build_reset_password_form_()
        self._build_request_reset_password_form_()
        self._build_change_password_form_()

    def _build_register_form_(self):
        if not self.settings.register_fields:
            self.settings.register_fields = [
                field.name for field in self.auth.table_user
                if field.type != 'id' and field.writable
            ]
        all_fieldkeys = [
            field.name for field in self.auth.table_user if field.name
            in self.settings.register_fields
        ]
        for i, fieldname in enumerate(all_fieldkeys):
            if fieldname == 'password':
                all_fieldkeys.insert(i+1, 'password2')
                break
        form_fields = {}
        for i, fieldname in enumerate(all_fieldkeys):
            if fieldname != 'password2':
                form_fields[fieldname] = \
                    self.auth.table_user[fieldname].clone()
            else:
                form_fields[fieldname] = Field(
                    'password', label=self.messages.verify_password
                )
            form_fields[fieldname]._inst_count_ = i
        self.form_data['register'] = form_fields

    def _build_retrieve_username_form_(self):
        form_fields = {
            'email': Field(
                validation={'is': 'email', 'presence': True},
                label='E-mail'
            )
        }
        self.form_data['retrieve_username'] = form_fields

    def _build_reset_password_form_(self):
        form_fields = {
            'password': self.auth.table_user['password'].clone(),
            'password2': Field(
                'password', label=self.messages.verify_password
            )
        }
        self.form_data['reset_password'] = form_fields

    def _build_request_reset_password_form_(self):
        userfield = self.settings.login_userfield
        if userfield == 'email':
            loginfield = Field(
                validation={'is': 'email', 'presence': True}
            )
        else:
            v = {'presence': True}
            if self.settings.username_case_sensitive:
                v['lower'] = True
            loginfield = Field(validation=v)
        form_fields = {
            userfield: loginfield
        }
        self.form_data['request_reset_password'] = form_fields

    def _build_change_password_form_(self):
        form_fields = {
            'old_password': self.auth.table_user['password'].clone(),
            'new_password': self.auth.table_user['password'].clone(),
            'new_password2': Field(
                'password', label=self.messages.verify_password
            )
        }
        form_fields['old_password'].label = self.messages.old_password
        form_fields['new_password'].lable = self.messages.new_password
        self.form_data['change_password'] = form_fields

    def login(self):
        return self.auth._login_with_handler(DefaultLoginHandler)

    def logout(self):
        nextv = (get_vars_next() or self.settings.logout_next or
                 self.auth.url('login'))
        onlogout = self.settings.logout_onlogout
        if onlogout:
            onlogout(self.auth.user)
        log = self.messages['logout_log']
        if self.auth.user:
            self.auth.log_event(log, self.auth.user)
        if self.settings.login_form != self.auth:
            cas = self.settings.login_form
            cas_user = cas.get_user()
            if cas_user:
                nextv = cas.logout_url(nextv)
        session.auth = None
        flash(self.messages.logged_out)
        if nextv is not None:
            redirect(nextv)

    def register(self):
        def process_form(form):
            if form.vars.password.password != form.vars.password2:
                form.errors.password = "password mismatch"
                form.errors.password2 = "password mismatch"
                return
            for validation in onvalidation:
                validation(form)

        if self.auth.is_logged_in():
            redirect(self.settings.url_logged or self.auth.url('profile'))
        nextv = get_vars_next() or self.settings.register_next
        onvalidation = self.settings.register_onvalidation
        onaccept = self.settings.register_onaccept
        log = self.messages['register_log']
        username = self.settings.login_userfield
        form = Form(
            self.form_data['register'],
            hidden=dict(_next=nextv),
            submit=self.messages.register_button,
            onvalidation=process_form,
            keepvalues=True
        )
        if form.accepted:
            del form.vars['password2']
            # insert user
            form.vars.id = self.auth.table_user.insert(**form.vars)
            row = self.auth.table_user(id=form.vars.id)
            description = self.messages.group_description % form.vars
            if self.settings.create_user_groups:
                group_id = self.auth.add_group(
                    self.settings.create_user_groups % form.vars, description)
                self.add_membership(group_id, form.vars.id)
            if self.settings.everybody_group_id:
                self.auth.add_membership(
                    self.settings.everybody_group_id, form.vars.id)
            if self.settings.registration_requires_verification:
                link = self.auth.url(
                    ['verify_email', row['registration_key']], scheme=True
                )
                d = dict(request.vars)
                d.update(dict(key=row['registration_key'], link=link,
                         username=form.vars[username]))
                if not (self.settings.mailer and self.settings.mailer.send(
                        to=form.vars.email,
                        subject=self.messages.verify_email_subject,
                        message=self.messages.verify_email % d)):
                    self.auth.db.rollback()
                    flash(self.messages.unable_send_email)
                    return form
                flash(self.messages.email_sent)
            if self.settings.registration_requires_approval and \
               not self.settings.registration_requires_verification:
                row.update_record(registration_key='pending')
                flash(self.messages.registration_pending)
            elif (not self.settings.registration_requires_verification or
                    self.settings.login_after_registration):
                flash(self.messages.registration_successful)
                self.auth.login_user(row)
                flash(self.messages.logged_in)
            self.auth.log_event(log, form.vars)
            callback(onaccept, form)
            if not nextv:
                nextv = self.auth.url('login')
            else:
                nextv = replace_id(nextv, form)
            redirect(nextv)
        return form

    def verify_email(self, key):
        user = self.auth.table_user(registration_key=key)
        if not user:
            redirect(self.settings.login_url or self.auth.url('login'))
        if self.settings.registration_requires_approval:
            user.update_record(registration_key='pending')
            flash(self.messages.registration_pending)
        else:
            user.update_record(registration_key='')
            flash(self.messages.email_verified)
        # make sure session has same user.registration_key as db record
        if self.auth.user:
            self.auth.user.registration_key = user.registration_key
        log = self.messages['verify_email_log']
        nextv = self.settings.verify_email_next or self.auth.url('login')
        onaccept = self.settings.verify_email_onaccept
        self.auth.log_event(log, user)
        callback(onaccept, user)
        redirect(nextv)

    def retrieve_username(self):
        if 'username' not in self.auth.table_user.fields:
            raise abort(404)
        if not self.settings.mailer:
            flash(self.messages.function_disabled)
            return ''
        nextv = get_vars_next() or self.settings.retrieve_username_next
        onvalidation = self.settings.retrieve_username_onvalidation
        onaccept = self.settings.retrieve_username_onaccept
        log = self.messages['retrieve_username_log']
        form = Form(
            self.form_data['retrieve_username'],
            hidden=dict(_next=nextv),
            sumbit=self.messages.submit_button,
            onvalidation=onvalidation
        )
        if form.accepted:
            users = self.auth.db(
                self.auth.table_user.email == form.vars.email).select()
            if not users:
                flash(self.messages.invalid_email)
                redirect(self.auth.url('retrieve_username'))
            username = ', '.join(u.username for u in users)
            self.settings.mailer.send(
                to=form.vars.email,
                subject=self.messages.retrieve_username_subject,
                message=self.messages.retrieve_username % dict(
                    username=username))
            flash(self.messages.email_sent)
            for user in users:
                self.auth.log_event(log, user)
            callback(onaccept, form)
            if not nextv:
                nextv = self.auth.url('retrieve_username')
            else:
                nextv = replace_id(nextv, form)
            redirect(nextv)
        return form

    def reset_password(self):
        def process_form(form):
            if form.vars.password.password != form.vars.password2:
                form.errors.password = self.messages.mismatched_password
                form.errors.password2 = self.messages.mismatched_password

        nextv = get_vars_next() or self.settings.reset_password_next
        try:
            key = request.vars.key
            t0 = int(key.split('-')[0])
            if time.time() - t0 > 60 * 60 * 24:
                raise Exception
            user = self.auth.table_user(reset_password_key=key)
            if not user:
                raise Exception
        except Exception:
            flash(self.messages.invalid_reset_password)
            redirect(nextv)
        form = Form(
            self.form_data['reset_password'],
            onvalidation=process_form,
            submit=self.messages.password_reset_button,
            hidden=dict(_next=nextv),
        )
        if form.accepted:
            user.update_record(
                password=str(form.vars.new_password),
                registration_key='',
                reset_password_key=''
            )
            flash(self.messages.password_changed)
            if self.settings.login_after_password_change:
                self.auth.login_user(user)
            redirect(nextv)
        return form

    def request_reset_password(self):
        def process_form(form, rows):
            field = self.settings.login_userfield
            user = self.auth.table_user(**{field: form.vars.email})
            rows['user'] = user
            if not user:
                form.errors[field] = self.messages['invalid_%s' % field]
                return
            for validation in onvalidation:
                validation(form)

        nextv = get_vars_next() or self.settings.request_reset_password_next
        if not self.settings.mailer:
            flash(self.messages.function_disabled)
            return ''
        onvalidation = self.settings.reset_password_onvalidation
        onaccept = self.settings.reset_password_onaccept
        log = self.messages['reset_password_log']
        rows = {}
        form = Form(
            self.form_data['request_reset_password'],
            hidden=dict(_next=nextv),
            submit=self.messages.password_reset_button,
            onvalidation=lambda form, rows=rows: process_form(form, rows)
        )
        if form.accepted:
            user = rows['user']
            if user.registration_key in ('pending', 'disabled', 'blocked'):
                flash(self.messages.registration_pending)
                redirect(self.auth.url('request_reset_password'))
            if self.auth.email_reset_password(user):
                flash(self.messages.email_sent)
            else:
                flash(self.messages.unable_to_send_email)
            self.auth.log_event(log, user)
            callback(onaccept, form)
            if not nextv:
                redirect(self.auth.url('request_reset_password'))
            else:
                nextv = replace_id(nextv, form)
            redirect(nextv)
        return form

    def retrieve_password(self):
        if self.settings.reset_password_requires_verification:
            return self.request_reset_password()
        else:
            return self.reset_password()

    def change_password(self):
        def process_form(form):
            if form.vars.old_password != row.password:
                form.errors.old_password = self.messages.invalid_password
                return
            if form.vars.new_password.password != form.vars.new_password2:
                form.errors.new_password = self.messages.mismatched_password
                form.errors.new_password2 = self.messages.mismatched_password
                return
            for validation in onvalidation:
                validation(form)

        if not self.auth.is_logged_in():
            redirect(self.settings.login_url or self.auth.url('login'))
        row = self.auth.table_user[self.auth.user.id]
        nextv = get_vars_next() or self.settings.change_password_next
        onvalidation = self.settings.change_password_onvalidation
        onaccept = self.settings.change_password_onaccept
        log = self.messages['change_password_log']
        form = Form(
            self.form_data['change_password'],
            onvalidation=process_form,
            submit=self.messages.password_change_button,
            hidden=dict(_next=nextv)
        )
        if form.accepted:
            row.update(password=str(form.vars.new_password))
            flash(self.messages.password_changed)
            self.auth.log_event(log, self.auth.user)
            callback(onaccept, form)
            if not nextv:
                nextv = self.auth.url('change_password')
            else:
                nextv = replace_id(nextv, form)
            redirect(nextv)
        return form

    def profile(self):
        if not self.auth.is_logged_in():
            redirect(self.settings.login_url)
        #passfield = self.settings.password_field
        nextv = get_vars_next() or self.settings.profile_next
        onvalidation = self.settings.profile_onvalidation
        onaccept = self.settings.profile_onaccept
        log = self.messages['profile_log']
        if not self.settings.profile_fields:
            self.settings.profile_fields = [
                field.name for field in self.auth.table_user
                if field.type != 'id' and field.writable]
        if 'password' in self.settings.profile_fields:
            self.settings.profile_fields.remove('password')
        form = DALForm(
            self.auth.table_user,
            record_id=self.auth.user.id,
            fields=self.settings.profile_fields,
            hidden=dict(_next=nextv),
            submit=self.messages.profile_save_button,
            upload=self.settings.download_url,
            onvalidation=onvalidation
        )
        if form.accepted:
            self.auth.user.update(
                self.auth.table_user._filter_fields(form.vars))
            flash(self.messages.profile_updated)
            self.auth.log_event(log, self.auth.user)
            callback(onaccept, form)
            ## TO-DO: update this
            #if form.deleted:
            #   return self.logout()
            if not nextv:
                nextv = self.auth.url('profile')
            else:
                nextv = replace_id(nextv, form)
            redirect(nextv)
        return form

    """
    ## REMOVED in 0.4
    def groups(self):
        #: displays the groups and their roles for the logged in user
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
    """

    def not_authorized(self):
        if request.isajax:
            raise abort(403, 'ACCESS DENIED')
        return 'ACCESS DENIED'
