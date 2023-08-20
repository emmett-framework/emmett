# -*- coding: utf-8 -*-
"""
    emmett.forms
    ------------

    Provides classes to create and style forms.

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Type, Union

from .ctx import current
from .datastructures import sdict
from .html import HtmlTag, tag, cat, asis
from .orm import Field, Model
from .orm.objects import Row, Table
from .security import CSRFStorage
from .utils import cachedprop
from .validators import isEmptyOr
from .wrappers.helpers import FileStorage

__all__ = ["Form", "ModelForm"]


class BaseForm(HtmlTag):
    @staticmethod
    def _get_default_style():
        return current.app.config.ui.forms_style or FormStyle

    def __init__(
        self,
        fields: List[Field],
        writable_fields: List[Field],
        csrf: Union[str, bool] = "auto",
        id_prefix: str = "",
        formstyle: Optional[Type[FormStyle]] = None,
        keepvalues: bool = False,
        onvalidation: Optional[Callable[[Form], None]] = None,
        submit: str = "Submit",
        upload: Optional[str] = None,
        _action: str = "",
        _enctype: str = "multipart/form-data",
        _method: str = "POST",
        **kwargs: Any
    ):
        self._action = _action
        self._csrf = csrf
        self._enctype = _enctype
        self._id_prefix = id_prefix
        self._formstyle = formstyle or self._get_default_style()
        self._submit_method = _method
        self._submit_text = submit
        self._upload = upload
        self.fields = fields
        self.keepvalues = keepvalues
        self.onvalidation = onvalidation
        self.writable_fields = writable_fields
        if not issubclass(self._formstyle, FormStyle):
            raise RuntimeError(
                "{!r} is an invalid Emmett form style".format(formstyle)
            )
        self._preprocess(**kwargs)

    def _preprocess(self, **kwargs):
        #: process attributes
        self.attributes = {
            "_action": self._action,
            "_enctype": self._enctype,
            "_method": self._submit_method,
            "id_prefix": self._id_prefix,
            "hidden": {},
            "submit": self._submit_text,
            "upload": self._upload
        }
        self.attributes.update(kwargs)
        #: init the form
        self._awaited = False
        self.input_params: sdict[str, Any] = sdict()
        self.errors: sdict[str, str] = sdict()
        self.params: sdict[str, Any] = sdict()
        self.files: sdict[str, FileStorage] = sdict()
        self.processed = False
        self.accepted = False
        self.formkey = "undef"

    @property
    def csrf(self) -> bool:
        return self._csrf is True or (
            self._csrf == "auto" and self._submit_method == "POST"
        )

    def _load_csrf(self):
        if not self.csrf:
            return
        if not hasattr(current, "session"):
            raise RuntimeError("You need sessions to use csrf in forms.")
        current.session._csrf = current.session._csrf or CSRFStorage()

    @property
    def _submitted(self):
        if self.csrf:
            return self.input_params._csrf_token in current.session._csrf
        return self.input_params._csrf_token == "undef"

    def _get_input_val(self, field):
        if field.type == "boolean":
            v = self.input_params.get(field.name, False)
            if v is not False:
                v = True
        elif field.type == "upload":
            v = self.input_files.get(field.name)
        else:
            v = self.input_params.get(field.name)
        return v

    def _validate_value(self, field, value):
        value, error = field.validate(value)
        if error:
            self.errors[field.name] = error
        elif field.type == "upload":
            self.files[field.name] = value
        else:
            self.params[field.name] = value

    async def _awaited_wrap(self):
        return self

    def __await__(self):
        if self._awaited:
            return self._awaited_wrap().__await__()
        self._awaited = True
        return self._process().__await__()

    async def _load_input_params(self):
        if self._submit_method == "POST":
            params = await current.request.body_params
        else:
            params = current.request.query_params
        return sdict(params)

    async def _load_input_files(self):
        if self._submit_method == "POST":
            rv = await current.request.files
        else:
            rv = sdict()
        return rv

    def _validate_input(self):
        for field in self.writable_fields:
            value = self._get_input_val(field)
            self._validate_value(field, value)

    async def _process(self, write_defaults=True):
        self._load_csrf()
        self.input_params = await self._load_input_params()
        self.input_files = await self._load_input_files()
        # run processing if needed
        if self._submitted:
            self.processed = True
            self._validate_input()
            # custom validation
            if not self.errors and callable(self.onvalidation):
                self.onvalidation(self)
            # end of validation
            if not self.errors:
                self.accepted = True
                if self.csrf:
                    del current.session._csrf[self.input_params._csrf_token]
        # CSRF protection logic
        if self.csrf and not self.accepted:
            self.formkey = current.session._csrf.gen_token()
        # reset default values in form
        if (
            write_defaults and (
                not self.processed or (self.accepted and not self.keepvalues)
            )
        ):
            for field in self.fields:
                self.input_params[field.name] = (
                    field.default() if callable(field.default) else
                    field.default
                )
        return self

    def _render(self):
        styler = self._formstyle(self.attributes)
        styler.on_start()
        for field in self.fields:
            value = self.input_params.get(field.name)
            error = self.errors.get(field.name)
            styler._proc_element(field, value, error)
        styler.add_buttons()
        styler._add_formkey(self.formkey)
        for key, value in self.attributes["hidden"].items():
            styler._add_hidden(key, value)
        return styler.render()

    @cachedprop
    def custom(self):
        # init
        custom = sdict()
        custom.dspval = sdict()
        custom.inpval = sdict()
        custom.label = sdict()
        custom.comment = sdict()
        custom.widget = sdict()
        # load selected styler
        styler = self._formstyle(self.attributes)
        styler.on_start()
        # load data
        for field in self.fields:
            value = self.input_params.get(field.name)
            custom.dspval[field.name] = self.input_params[field.name]
            custom.inpval[field.name] = self.input_params[field.name]
            custom.label[field.name] = field.label
            custom.comment[field.name] = field.comment
            widget, wfield = styler._get_widget(field, value)
            if not wfield:
                styler.style_widget(widget)
            custom.widget[field.name] = widget
        # add submit
        custom.submit = tag.input(_type="submit", value=self.attributes["submit"])
        # provides begin attribute
        custom.begin = asis(f"<form {self._build_html_attributes()}>")
        # add hidden stuffs to get process working
        hidden = cat()
        hidden.append(
            tag.input(_name="_csrf_token", _type="hidden", _value=self.formkey)
        )
        for key, value in self.attributes["hidden"].items():
            hidden.append(tag.input(_name=key, _type="hidden", _value=value)
        )
        # provides end attribute
        custom.end = asis(f"{hidden.__html__()}</form>")
        return custom

    def __html__(self):
        return self._render().__html__()


class Form(BaseForm):
    def __init__(
        self,
        fields: Optional[Dict[str, Field]] = None,
        csrf: Union[str, bool] = "auto",
        id_prefix: str = "",
        formstyle: Optional[Type[FormStyle]] = None,
        keepvalues: bool = False,
        onvalidation: Optional[Callable[[Form], None]] = None,
        submit: str = "Submit",
        upload: Optional[str] = None,
        _action: str = "",
        _enctype: str = "multipart/form-data",
        _method: str = "POST",
        **kwargs: Any
    ):
        fields = fields or {}
        #: get fields from kwargs
        for name, parameter in kwargs.items():
            if isinstance(parameter, Field):
                fields[name] = parameter
        for name in fields.keys():
            if name in kwargs:
                del kwargs[name]
        #: order fields correctly
        sorted_fields = []
        for name, field in fields.items():
            sorted_fields.append((name, field))
        sorted_fields.sort(key=lambda tup: tup[1]._inst_count_)
        #: init fields
        fields_list_all = []
        fields_list_writable = []
        for name, obj in sorted_fields:
            field_obj = obj._make_field(name)
            fields_list_all.append(field_obj)
            if field_obj.writable:
                fields_list_writable.append(field_obj)
        super().__init__(
            fields=fields_list_all,
            writable_fields=fields_list_writable,
            csrf=csrf,
            id_prefix=id_prefix,
            formstyle=formstyle,
            keepvalues=keepvalues,
            onvalidation=onvalidation,
            submit=submit,
            upload=upload,
            _action=_action,
            _enctype=_enctype,
            _method=_method
        )


class ModelForm(BaseForm):
    def __init__(
        self,
        model: Type[Model],
        record: Optional[Row] = None,
        record_id: Any = None,
        fields: Union[Dict[str, List[str]], List[str]] = None,
        exclude_fields: List[str] = [],
        csrf: Union[str, bool] = "auto",
        formstyle: Optional[Type[FormStyle]] = None,
        keepvalues: bool = False,
        onvalidation: Optional[Callable[[Form], None]] = None,
        submit: str = "Submit",
        upload: Optional[str] = None,
        _action: str = "",
        _enctype: str = "multipart/form-data",
        _method: str = "POST",
        **attributes
    ):
        self.model = model._instance_()
        self.table: Table = self.model.table
        self.record = record or (
            self.model.get(record_id) if record_id else
            self.model.new()
        )
        #: build fields for form
        fields_list_all = []
        fields_list_writable = []
        if fields is not None:
            #: developer has selected specific fields
            if not isinstance(fields, dict):
                fields = {'writable': fields, 'readable': fields}
            for field in self.table:
                if field.name not in fields['readable']:
                    continue
                fields_list_all.append(field)
                if field.name in fields['writable']:
                    fields_list_writable.append(field)
        else:
            #: use table fields
            for field in self.table:
                if field.name in exclude_fields:
                    continue
                if not field.readable:
                    continue
                if not self.record and not field.writable:
                    #: show readable fields only on update
                    continue
                fields_list_all.append(field)
                if field.writable:
                    fields_list_writable.append(field)
        super().__init__(
            fields=fields_list_all,
            writable_fields=fields_list_writable,
            csrf=csrf,
            id_prefix=self.table._tablename + "_",
            formstyle=formstyle,
            keepvalues=keepvalues,
            onvalidation=onvalidation,
            submit=submit,
            upload=upload,
            _action=_action,
            _enctype=_enctype,
            _method=_method
        )

    def _get_id_value(self):
        if len(self.model._fieldset_pk) > 1:
            return tuple(self.record[pk] for pk in self.model.primary_keys)
        return self.record[self.table._id.name]

    def _validate_input(self):
        record, fields = self.record.clone(), {
            field.name: self._get_input_val(field)
            for field in self.writable_fields
        }
        for field in filter(lambda f: f.type == "upload", self.writable_fields):
            val = fields[field.name]
            if (
                (val == b"" or val is None) and
                not self.input_params.get(field.name + "__del", False) and
                self.record[field.name]
            ):
                fields.pop(field.name)
        record.update(fields)
        errors = record.validation_errors
        for field in self.writable_fields:
            if field.name in errors:
                self.errors[field.name] = errors[field.name]
            elif field.type == "upload":
                self.files[field.name] = fields[field.name]
            else:
                self.params[field.name] = fields[field.name]

    async def _process(self, **kwargs):
        #: send record id to validators if needed
        current._dbvalidation_record_id_ = None
        if self.record._concrete:
            current._dbvalidation_record_id_ = self._get_id_value()
        #: load super `_process`
        await super()._process(write_defaults=False)
        #: additional record logic
        if self.accepted:
            #: handle uploads
            for field in filter(lambda f: f.type == "upload", self.writable_fields):
                upload = self.files[field.name]
                del_field = field.name + "__del"
                if not upload.filename:
                    if self.input_params.get(del_field, False):
                        self.params[field.name] = self.table[field.name].default or ""
                        # TODO: do we want to physically delete file?
                    else:
                        if self.record._concrete and self.record[field.name]:
                            self.params[field.name] = self.record[field.name]
                    continue
                else:
                    source_file, original_filename = upload.stream, upload.filename
                newfilename = field.store(
                    source_file, original_filename, field.uploadfolder
                )
                if isinstance(field.uploadfield, str):
                    self.params[field.uploadfield] = source_file.read()
                self.params[field.name] = newfilename
            #: perform save
            self.record.update(self.params)
            if self.record.save():
                self.params.id = self._get_id_value()
        #: clear current from validation data
        del current._dbvalidation_record_id_
        #: cleanup inputs
        if not self.processed or (self.accepted and not self.keepvalues):
            for field in self.fields:
                self.input_params[field.name] = field.formatter(
                    self.record[field.name]
                )
        elif self.processed and not self.accepted and self.record._concrete:
            for field in self.writable_fields:
                if field.type == "upload" and field.name not in self.params:
                    self.input_params[field.name] = field.formatter(
                        self.record[field.name]
                    )
        return self


class FormStyle:
    _stack = []
    parent = None

    @staticmethod
    def _field_options(field):
        validator = FormStyle._validation_woptions(field)
        return validator.options(), validator.multiple

    @staticmethod
    def widget_string(attr, field, value, _class="string", _id=None):
        return tag.input(
            _type="text",
            _name=field.name,
            _value=value if value is not None else "",
            _class=_class,
            _id=_id or field.name
        )

    @staticmethod
    def widget_text(attr, field, value, _class="text", _id=None):
        return tag.textarea(
            value or "",
            _name=field.name,
            _class=_class,
            _id=_id or field.name
        )

    @staticmethod
    def widget_int(attr, field, value, _class="int", _id=None):
        return FormStyle.widget_string(attr, field, value, _class, _id)

    @staticmethod
    def widget_bigint(attr, field, value, _class="int", _id=None):
        return FormStyle.widget_string(attr, field, value, _class, _id)

    @staticmethod
    def widget_float(attr, field, value, _class="float", _id=None):
        return FormStyle.widget_string(attr, field, value, _class, _id)

    @staticmethod
    def widget_date(attr, field, value, _class="date", _id=None):
        return tag.input(
            _type="date",
            _name=field.name,
            _value=value if value is not None else "",
            _class=_class,
            _id=_id or field.name
        )

    @staticmethod
    def widget_time(attr, field, value, _class="time", _id=None):
        return tag.input(
            _type="time",
            _name=field.name,
            _value=value if value is not None else "",
            _class=_class,
            _id=_id or field.name
        )

    @staticmethod
    def widget_datetime(attr, field, value, _class="datetime", _id=None):
        return tag.input(
            _type="datetime-local",
            _name=field.name,
            _value=value if value is not None else "",
            _class=_class,
            _id=_id or field.name
        )

    @staticmethod
    def widget_password(attr, field, value, _class="password", _id=None):
        return tag.input(
            _type="password",
            _name=field.name,
            _value=value or "",
            _class=_class,
            _id=_id or field.name
        )

    @staticmethod
    def widget_bool(attr, field, value, _class="bool", _id=None):
        return tag.input(
            _type="checkbox",
            _name=field.name,
            _checked="checked" if value else None,
            _class=_class,
            _id=_id or field.name
        )

    @staticmethod
    def widget_select(attr, field, value, _class="", _id=None):
        def selected(k):
            return "selected" if str(value) == str(k) else None

        options, multiple = FormStyle._field_options(field)
        if multiple:
            return FormStyle.widget_multiple(
                attr, field, value, options, _class=_class, _id=_id
            )
        return tag.select(
            *[
                tag.option(n, _value=k, _selected=selected(k)) for k, n in options
            ],
            _name=field.name,
            _class=_class,
            _id=_id or field.name
        )

    @staticmethod
    def widget_multiple(attr, field, values, options, _class="", _id=None):
        def selected(k):
            return "selected" if str(k) in [str(v) for v in values] else None

        values = values or []
        return tag.select(
            *[
                tag.option(n, _value=k, _selected=selected(k)) for k, n in options
            ],
            _name=field.name,
            _class=_class,
            _multiple="multiple",
            _id=_id or field.name
        )

    @staticmethod
    def widget_list(field, value, _id=None):
        options, _ = FormStyle._field_options(field)
        return FormStyle.widget_multiple(None, field, value, options, _id=_id)

    @staticmethod
    def widget_upload(attr, field, value, _class="upload", _id=None):
        def is_image(value):
            return value.split(".")[-1].lower() in ["gif", "png", "jpg", "jpeg", "bmp"]

        def _coerce_value(value):
            if isinstance(value, str) or isinstance(value, bytes):
                return value or ""
            return ""

        elements = []
        _value = _coerce_value(value)
        download_url = attr.get("upload")
        inp = tag.input(_type="file", _name=field.name, _class=_class, _id=_id)
        elements.append(inp)
        if _value and download_url:
            if callable(download_url):
                url = download_url(value)
            else:
                url = download_url + "/" + value
            if is_image(_value):
                elements.append(tag.img(_src=url, _width="120px", _class="upload_img"))
            else:
                elements.append(tag.div(tag.a(_value, _href=url)))
            requires = field.requires or []
            # delete checkbox
            if not requires or any(isinstance(v, isEmptyOr) for v in requires):
                elements.append(
                    tag.div(
                        tag.input(
                            _type="checkbox",
                            _class="checkbox",
                            _id=_id + "__del",
                            _name=field.name + "__del",
                            _style="display: inline;"
                        ),
                        tag.label(
                            "delete",
                            _for=_id + "__del",
                            _style="margin: 4px"
                        ),
                        _style="white-space: nowrap;"
                    )
                )
        return tag.div(*elements, _class="upload_wrap")

    @staticmethod
    def widget_json(attr, field, value, _id=None):
        return FormStyle.widget_text(attr, field, value, _id=_id or field.name)

    @staticmethod
    def widget_jsonb(attr, field, value, _id=None):
        return FormStyle.widget_text(attr, field, value, _id=_id or field.name)

    @staticmethod
    def widget_radio(field, value):
        options, _ = FormStyle._field_options(field)
        return cat(*[
            tag.div(
                tag.input(
                    _id=f"{field.name}_{k}",
                    _name=field.name,
                    _value=k,
                    _type="radio",
                    _checked=("checked" if str(k) == str(value) else None)
                ),
                tag.label(n, _for=f"{field.name}_{k}"),
                _class="option_wrap"
            ) for k, n in options
        ])

    def __init__(self, attributes):
        self.attr = attributes

    @staticmethod
    def _validation_woptions(field):
        ftype = field._type.split(":")[0]
        if ftype != "bool" and field.requires:
            for v in field.requires:
                if hasattr(v, "options"):
                    return v
        return None

    #: returns the widget for the field and a boolean (True if widget is
    #  defined by user, False if it comes from styler default ones)
    def _get_widget(self, field, value):
        if field.widget:
            return field.widget(field, value), True
        widget_id = self.attr["id_prefix"] + field.name
        wtype = field._type.split(":")[0]
        if self._validation_woptions(field) is not None:
            wtype = "select"
        elif wtype.startswith("reference"):
            wtype = "int"
        elif wtype.startswith("decimal"):
            wtype = "float"
        try:
            widget = getattr(self, "widget_" + wtype)(
                self.attr, field, value, _id=widget_id
            )
            if not field.writable:
                self._disable_widget(widget)
            return widget, False
        except AttributeError:
            raise RuntimeError(
                f"Missing form widget for field {field.name} of type {wtype}"
            )

    def _disable_widget(self, widget):
        widget.attributes["_disabled"] = "disabled"

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
        self.parent.append(tag.input(_name=key, _type="hidden", _value=value))

    def _add_formkey(self, key):
        self.parent.append(tag.input(_name="_csrf_token", _type="hidden", _value=key))

    @property
    def element(self):
        return self._stack[-1] if self._stack else None

    def on_start(self):
        self.parent = cat()

    def style_widget(self, widget):
        pass

    def create_label(self, label):
        return tag.label(label, _for=self.element.widget["_id"], _class="emt_label")

    def create_error(self, error):
        return tag.div(error, _class="emt_error")

    def create_comment(self, comment):
        return tag.p(comment, _class="emt_help")

    def add_widget(self, widget):
        wrapper = tag.div(widget)
        if self.element.error:
            wrapper.append(self.element.error)
        if self.element.comment:
            wrapper.append(self.element.comment)
        self.parent.append(tag.div(self.element.label, wrapper))

    def add_buttons(self):
        submit = tag.input(_type="submit", _value=self.attr["submit"])
        self.parent.append(tag.div(submit))

    def render(self):
        return tag.form(self.parent, **self.attr)


def add_form_on_model(cls):
    @wraps(cls)
    def wrapped(model, *args, **kwargs):
        return cls(model, *args, **kwargs)
    return wrapped


setattr(Model, "form", classmethod(add_form_on_model(ModelForm)))
