# -*- coding: utf-8 -*-
"""
    weppy.forms
    -----------

    Provides classes to create and style forms in weppy.

    :copyright: (c) 2015 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

import uuid

from ._compat import iteritems, iterkeys
from .dal import Field
from .datastructures import sdict
from .globals import current, request, session
from .tags import tag, TAG, cat, asis

__all__ = ['Form', 'DALForm']


class Form(TAG):
    default_attrs = {
        '_action': '', '_method': 'POST', '_enctype': 'multipart/form-data',
        'submit': 'Submit', 'csrf': 'auto', 'keepvalues': False,
        'onvalidation': None, 'id_prefix': '', 'upload': None
    }

    @staticmethod
    def _get_default_style():
        from .expose import Expose
        return Expose.application.config.ui.forms_style or FormStyle

    def __init__(self, fields={}, **kwargs):
        #: get fields from kwargs
        for name, parameter in iteritems(kwargs):
            if isinstance(parameter, Field):
                fields[name] = parameter
        for name in iterkeys(fields):
            if name in kwargs:
                del kwargs[name]
        #: order fields correctly
        sorted_fields = []
        for name, field in iteritems(fields):
            sorted_fields.append((name, field))
        sorted_fields.sort(key=lambda x: x[1]._inst_count_)
        #: init fields
        self.fields = []
        for name, obj in sorted_fields:
            self.fields.append(obj._make_field(name))
        self._preprocess_(**kwargs)

    def _preprocess_(self, **kwargs):
        #: process attributes
        self.attributes = {}
        for key, val in Form.default_attrs.items():
            self.attributes[key] = kwargs.get(key, val)
        self.attributes['formstyle'] = self.attributes.get(
            'formstyle', self._get_default_style())
        #: init the form
        self.errors = sdict()
        self.vars = sdict()
        self.input_vars = None
        self.processed = False
        self.accepted = False
        self.formkey = "undef"
        #: move some attributes to self, just because it's handy
        self.keepvalues = self.attributes['keepvalues']
        self.onvalidation = self.attributes['onvalidation']
        del self.attributes['keepvalues']
        del self.attributes['onvalidation']
        #: verify formstyle consistence
        if not issubclass(self.attributes['formstyle'], FormStyle):
            raise RuntimeError('%s is an invalid weppy form style'
                               % self.attributes['formstyle'].__name__)
        #: process the form
        self._process()

    @property
    def csrf(self):
        _csrf = self.attributes["csrf"]
        return _csrf is True or (_csrf == 'auto' and
                                 self.attributes['_method'] == 'POST')

    def _load_csrf(self):
        if not self.csrf:
            return
        if not hasattr(current, "session"):
            raise RuntimeError("You need sessions to use csrf in forms.")
        session._csrf_tokens = session._csrf_tokens or {}
        #: some clean up of session
        if len(session._csrf_tokens) > 10:
            session._csrf_tokens = {}

    @property
    def _submitted(self):
        if self.csrf:
            return self.input_vars._csrf_token in session._csrf_tokens
        return self.input_vars._csrf_token is 'undef'

    def _get_input_val(self, field):
        if field.type == 'boolean':
            v = self.input_vars.get(field.name, False)
            if v is not False:
                v = True
        else:
            v = self.input_vars.get(field.name)
        return v

    def _process(self):
        self._load_csrf()
        method = self.attributes['_method']
        # get appropriate input variables
        if method is "POST":
            self.input_vars = sdict(request.post_vars)
        else:
            self.input_vars = sdict(request.get_vars)
        # run processing if needed
        if self._submitted:
            self.processed = True
            # validate input
            for field in self.fields:
                value = self._get_input_val(field)
                value, error = field.validate(value)
                if error:
                    self.errors[field.name] = error
                else:
                    self.vars[field.name] = value
            # custom validation
            if not self.errors and callable(self.onvalidation):
                self.onvalidation(self)
            # end of validation
            if not self.errors:
                self.accepted = True
                if self.csrf:
                    del session._csrf_tokens[self.input_vars._csrf_token]
        # CRSF protection logic
        if self.csrf and not self.accepted:
            token = str(uuid.uuid4())
            session._csrf_tokens[token] = 1
            self.formkey = token
        # reset default values in form
        if not self.processed or (self.accepted and not self.keepvalues):
            for field in self.fields:
                default_value = field.default() if callable(field.default) \
                    else field.default
                self.input_vars[field.name] = default_value

    def _render(self):
        styler = self.attributes['formstyle'](self.attributes)
        styler.on_start()
        for field in self.fields:
            value = self.input_vars.get(field.name)
            error = self.errors.get(field.name)
            styler._proc_element(field, value, error)
        styler.add_buttons()
        styler._add_formkey(self.formkey)
        for key, value in iteritems(self.attributes.get('hidden', {})):
            styler._add_hidden(key, value)
        return styler.render()

    @property
    def custom(self):
        if not hasattr(self, '_custom'):
            # init
            self._custom = custom = sdict()
            custom.dspval = sdict()
            custom.inpval = sdict()
            custom.label = sdict()
            custom.comment = sdict()
            custom.widget = sdict()
            # load selected styler
            styler = self.attributes['formstyle'](self.attributes)
            styler.on_start()
            # load data
            for field in self.fields:
                value = self.input_vars.get(field.name)
                custom.dspval[field.name] = self.input_vars[field.name]
                custom.inpval[field.name] = self.input_vars[field.name]
                custom.label[field.name] = field.label
                custom.comment[field.name] = field.comment
                widget, wfield = styler._get_widget(field, value)
                if not wfield:
                    styler.style_widget(widget)
                custom.widget[field.name] = widget
            # add submit
            custom.submit = tag.input(_type="submit",
                                      value=self.attributes['submit'])
            # provides begin attribute
            begin = '<form action="%s" method="%s" enctype="%s">' % \
                (self.attributes['_action'],
                 self.attributes['_method'],
                 self.attributes['_enctype'])
            custom.begin = asis(begin)
            # add hidden stuffs to get weppy process working
            hidden = cat()
            hidden.append(tag.input(_name='_csrf_token', _type='hidden',
                                    _value=self.formkey))
            for key, value in iteritems(self.attributes.get('hidden', {})):
                hidden.append(tag.input(_name=key, _type='hidden',
                              _value=value))
            # provides end attribute
            end = '%s</form>' % hidden.to_html()
            custom.end = asis(end)
        return self._custom

    def to_html(self):
        return self._render().to_html()


class DALForm(Form):
    def __init__(self, table, record=None, record_id=None, fields=None,
                 exclude_fields=[], **attributes):
        self.table = table
        self.record = record or table(record_id)
        #: build fields for form
        self.fields = []
        if fields is not None:
            #: developer has selected specific fields
            for field in fields:
                self.fields.append(table[field])
        else:
            #: use table fields
            for field in table:
                if field.type != 'id' and field.writable and \
                        field.name not in exclude_fields:
                    self.fields.append(field)
        #: use tablename for form id
        attributes['id_prefix'] = table._tablename+"_"
        #: finally init the form
        self._preprocess_(**attributes)

    def _process(self):
        #: send record id to validators if needed
        current._form_validation_record_id_ = None
        if self.record:
            current._form_validation_record_id_ = self.record.id
        #: load super `_process`
        Form._process(self)
        #: clear current and run additional operations for DAL
        del current._form_validation_record_id_
        if self.accepted:
            for field in self.fields:
                #: handle uploads
                if field.type == 'upload':
                    f = self.vars[field.name]
                    fd = field.name+"__del"
                    if f == '' or f is None:
                        if self.input_vars.get(fd, False):
                            self.vars[field.name] = \
                                self.table[field.name].default or ''
                            ## TODO?: we want to physically delete file?
                        else:
                            if self.record and self.record[field.name]:
                                self.vars[field.name] = self.record[field.name]
                        continue
                    elif hasattr(f, 'file'):
                        source_file, original_filename = f.file, f.filename
                    else:
                        continue
                    newfilename = field.store(source_file, original_filename,
                                              field.uploadfolder)
                    if isinstance(field.uploadfield, str):
                        self.vars[field.uploadfield] = source_file.read()
                    self.vars[field.name] = newfilename
            #: add default values to hidden fields if needed
            ffields = [field.name for field in self.fields]
            for field in self.table:
                if field.name not in ffields and field.writable is False \
                        and field.update is None and field.compute is None:
                    if not self.record and field.default is not None:
                        def_val = field.default() if callable(field.default) \
                            else field.default
                        self.vars[field.name] = def_val
            if self.record:
                self.record.update_record(**self.vars)
            else:
                self.vars.id = self.table.insert(**self.vars)
        if not self.processed or (self.accepted and not self.keepvalues):
            for field in self.fields:
                if self.record:
                    self.input_vars[field.name] = self.record[field.name]
                self.input_vars[field.name] = field.formatter(
                    self.input_vars[field.name])


class FormStyle(object):
    _stack = []
    parent = None

    @staticmethod
    def _field_options(field):
        def represent(value):
            if value and field.represent:
                return field.represent(value)
            return value

        options = field.requires[0].options()
        option_items = [(k, represent(n)) for k, n in options]
        return option_items

    @staticmethod
    def widget_string(attr, field, value, _class='string', _id=None):
        return tag.input(
            _type='text', _name=field.name, _value=value or '',
            _class=_class, _id=_id or field.name
        )

    @staticmethod
    def widget_text(attr, field, value, _class='text', _id=None):
        return tag.textarea(value or '', _name=field.name,
                            _class=_class, _id=_id or field.name)

    @staticmethod
    def widget_int(attr, field, value, _class='int', _id=None):
        return FormStyle.widget_string(attr, field, value, _class, _id)

    @staticmethod
    def widget_float(attr, field, value, _class='float', _id=None):
        return FormStyle.widget_string(attr, field, value, _class, _id)

    @staticmethod
    def widget_date(attr, field, value, _class='date', _id=None):
        return FormStyle.widget_string(attr, field, value, _class, _id)

    @staticmethod
    def widget_time(attr, field, value, _class='time', _id=None):
        return FormStyle.widget_string(attr, field, value, _class, _id)

    @staticmethod
    def widget_datetime(attr, field, value, _class='datetime', _id=None):
        return FormStyle.widget_string(attr, field, value, _class, _id)

    @staticmethod
    def widget_password(attr, field, value, _class='password', _id=None):
        return tag.input(
            _type='password', _name=field.name, _value=value or '',
            _class=_class, _id=_id or field.name
        )

    @staticmethod
    def widget_bool(attr, field, value, _class='bool', _id=None):
        return tag.input(_type='checkbox', _name=field.name,
                         _checked='checked' if value else None,
                         _class=_class, _id=_id or field.name)

    @staticmethod
    def widget_select(attr, field, value, _class='', _id=None):
        def selected(k):
            return 'selected' if str(value) == str(k) else None

        options = FormStyle._field_options(field)
        if field.requires[0].multiple:
            return FormStyle.widget_multiple(attr, field, value, options,
                                             _class=_class, _id=_id)
        option_items = [tag.option(n, _value=k, _selected=selected(k))
                        for k, n in options]
        return tag.select(*option_items, _name=field.name, _class=_class,
                          _id=_id or field.name)

    @staticmethod
    def widget_multiple(attr, field, values, options, _class='', _id=None):
        def selected(k):
            return 'selected' if str(k) in [str(v) for v in values] else None

        values = values or []
        option_items = [tag.option(n, _value=k, _selected=selected(k))
                        for k, n in options]
        return tag.select(*option_items, _name=field.name, _class=_class,
                          multiple='multiple', _id=_id or field.name)

    #: TO-DO
    #@staticmethod
    #def widget_list(attr, field, value, _class='', _id=None):
    #    return ""

    @staticmethod
    def widget_upload(attr, field, value, _class='upload',
                      _id=None):
        def is_image(value):
            extension = value.split('.')[-1].lower()
            if extension in ['gif', 'png', 'jpg', 'jpeg', 'bmp']:
                return True
            return False
        elements = []
        _value = value or ''
        download_url = attr.get('upload')
        inp = tag.input(_type='file', _name=field.name, _class=_class, _id=_id)
        elements.append(inp)
        if _value and download_url:
            if callable(download_url):
                url = download_url(value)
            else:
                url = download_url + '/' + value
            if is_image(_value):
                elements.append(tag.img(_src=url, _width='120px',
                                        _class='upload_img'))
            else:
                elements.append(tag.div(tag.a(_value, _href=url)))
            requires = field.requires or []
            # delete checkbox
            from .validators import isEmptyOr
            if not requires or (isinstance(v, isEmptyOr) for v in requires):
                elements.append(tag.div(
                    tag.input(_type='checkbox', _class='checkbox',
                              _id=_id+'__del', _name=field.name+'__del',
                              _style="display: inline;"),
                    tag.label('delete', _for=_id+'__del',
                              _style="margin: 4px"),
                    _style="white-space: nowrap;"))
        return tag.div(*elements, _class='upload_wrap')

    @staticmethod
    def widget_json(attr, field, value, _id=None):
        return FormStyle.widget_text(attr, field, value, _id=_id or field.name)

    def __init__(self, attributes):
        self.attr = attributes

    #: returns the widget for the field and a boolean (True if widget is
    #  defined by user, False if it comes from styler default ones)
    def _get_widget(self, field, value):
        if field.widget:
            return field.widget(field, value), True
        wtype = field._type.split(":")[0]
        if wtype != 'bool' and len(field.requires) and \
                hasattr(field.requires[0], 'options'):
            wtype = 'select'
        elif wtype.startswith('reference'):
            wtype = 'int'
        widget_id = self.attr["id_prefix"] + field.name
        try:
            return getattr(self, "widget_"+wtype)(
                self.attr, field, value, _id=widget_id), False
        except AttributeError:
            raise RuntimeError("Missing form widget for field %s of type %s" %
                               (field.name, wtype))

    def _proc_element(self, field, value, error):
        widget, wfield = self._get_widget(field, value)
        self._stack.append(sdict(widget=widget, _wffield=wfield))
        self._add_element(field.label, field.comment, error)
        self._stack.pop(-1)

    def _add_element(self, label, comment, error):
        # style only widgets not defined by user
        if not self.element._wffield:
            self.style_widget(self.element.widget)
        self.element.label = self.create_label(label)
        if comment:
            self.element.comment = self.create_comment(comment)
        if error:
            self.element.error = self.create_error(error)
        self.add_widget(self.element.widget)

    def _add_hidden(self, key, value):
        self.parent.append(tag.input(_name=key, _type='hidden', _value=value))

    def _add_formkey(self, key):
        self.parent.append(tag.input(_name='_csrf_token', _type='hidden',
                                     _value=key))

    @property
    def element(self):
        return self._stack[-1] if self._stack else None

    def on_start(self):
        self.parent = cat()

    def style_widget(self, widget):
        pass

    def create_label(self, label):
        wid = self.element.widget['_id']
        return tag.label(label, _for=wid, _class='wpp_label')

    def create_error(self, error):
        return tag.div(error, _class='wpp_error')

    def create_comment(self, comment):
        return tag.p(comment, _class='wpp_help')

    def add_widget(self, widget):
        wrapper = tag.div(widget)
        if self.element.error:
            wrapper.append(self.element.error)
        if self.element.comment:
            wrapper.append(self.element.comment)
        self.parent.append(tag.div(self.element.label, wrapper))

    def add_buttons(self):
        submit = tag.input(_type='submit', _value=self.attr['submit'])
        self.parent.append(tag.div(submit))

    def render(self):
        return tag.form(self.parent, **self.attr)
