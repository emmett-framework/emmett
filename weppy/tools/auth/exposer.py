from ...dal import Field
from ...forms import Form, DALForm
from ...globals import request, session
from ...helpers import flash
from ...http import HTTP, redirect
from ...tags import tag
from .defaults import DEFAULT
from .handlers import DefaultLoginHandler
from .helpers import callback, replace_id, get_vars_next


class Exposer(object):
    def __init__(self, auth):
        self.auth = auth
        self.settings = auth.settings
        self.messages = auth.messages
        self.form_data = {}
        self._build_register_form_()

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

    def login(self):
        return self.auth._login_with_handler(DefaultLoginHandler)

    def logout(self):
        nextv = get_vars_next() or self.settings.logout_next
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
                onvalidation(form)

        #usermodel = self.settings.models.user
        if self.auth.is_logged_in():
            redirect(self.settings.url_logged or self.auth.url('profile'))
        nextv = get_vars_next() or self.settings.register_next
        onvalidation = self.settings.register_onvalidation
        onaccept = self.settings.register_onaccept
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

        form = Form(
            self.form_data['register'],
            hidden=dict(_next=nextv),
            submit=self.messages.register_button,
            onvalidation=process_form,
            keepvalues=True
        )
        #self.table_user.registration_key.default = key = uuid()
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
                self.auth.table_user[form.vars.id] = dict(
                    registration_key='pending')
                flash(self.messages.registration_pending)
            elif (not self.settings.registration_requires_verification or
                    self.settings.login_after_registration):
                if not self.settings.registration_requires_verification:
                    #self.auth.table_user[form.vars.id] = dict(registration_key='')
                    row.update_record(registration_key='')
                flash(self.messages.registration_successful)
                #user = self.auth.table_user(**{username: form.vars[username]})
                #self.auth.login_user(user)
                self.auth.login_user(row)
                flash(self.messages.logged_in)
            self.auth.log_event(log, form.vars)
            callback(onaccept, form)
            if not nextv:
                nextv = self.auth.url('login')
            else:
                nextv = replace_id(nextv, form)
            redirect(nextv)
                    #client_side=self.settings.client_side)
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

    # NEEDS REFACTOR
    def retrieve_username(self, next=DEFAULT, onvalidation=DEFAULT,
                          onaccept=DEFAULT, log=DEFAULT):
        from ..validators._old import inDb
        if not 'username' in self.table_user.fields:
            raise HTTP(404)
        #captcha = self.settings.retrieve_username_captcha or \
        #        (self.settings.retrieve_username_captcha != False and self.settings.captcha)
        if not self.settings.mailer:
            response.flash = self.messages.function_disabled
            return ''
        if next is DEFAULT:
            next = get_vars_next() or self.settings.retrieve_username_next
        if onvalidation is DEFAULT:
            onvalidation = self.settings.retrieve_username_onvalidation
        if onaccept is DEFAULT:
            onaccept = self.settings.retrieve_username_onaccept
        if log is DEFAULT:
            log = self.messages['retrieve_username_log']
        email_field = self.table_user.email.clone()
        email_field.requires = [
            inDb(self.db, self.table_user.email,
                 message=self.messages.invalid_email)]
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

    # NEEDS REFACTOR
    def reset_password(self, next=DEFAULT, onvalidation=DEFAULT,
                       onaccept=DEFAULT, log=DEFAULT):
        import time

        def _same_psw(value):
            if value != request.vars.new_password:
                return (value, mismatch_psw_msg)
            return (value, None)
        mismatch_psw_msg = self.messages.mismatched_password

        if next is DEFAULT:
            next = get_vars_next() or self.settings.reset_password_next
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

    # NEEDS REFACTOR
    def request_reset_password(self, next=DEFAULT, onvalidation=DEFAULT,
                               onaccept=DEFAULT, log=DEFAULT):
        from ..validators import isEmail
        from ..validators._old import inDb
        #captcha = self.settings.retrieve_password_captcha or \
        #        (self.settings.retrieve_password_captcha != False and self.settings.captcha)

        if next is DEFAULT:
            next = get_vars_next() or self.settings.request_reset_password_next
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
            req = [isEmail(message=self.messages.invalid_email),
                   inDb(self.db, self.table_user.email,
                        message=self.messages.invalid_email)]
        else:
            req = [inDb(self.db, self.table_user.username,
                        message=self.messages.invalid_username)]
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

    # NEEDS REFACTOR
    def retrieve_password(self, next=DEFAULT, onvalidation=DEFAULT,
                          onaccept=DEFAULT, log=DEFAULT):
        if self.settings.reset_password_requires_verification:
            return self.request_reset_password(next, onvalidation, onaccept,
                                               log)
        else:
            return self.reset_password(next, onvalidation, onaccept, log)

    # NEEDS REFACTOR
    def change_password(self, next=DEFAULT, onvalidation=DEFAULT,
                        onaccept=DEFAULT, log=DEFAULT):
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
            next = get_vars_next() or self.settings.change_password_next
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
            self.auth.user.update(self.auth.table_user._filter_fields(form.vars))
            flash(self.messages.profile_updated)
            self.log_event(log, self.auth.user)
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

    # NEEDS REFACTOR
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

    def not_authorized(self):
        if request.isajax:
            raise HTTP(403, 'ACCESS DENIED')
        return 'ACCESS DENIED'
