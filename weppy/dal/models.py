# -*- coding: utf-8 -*-
"""
    weppy.dal.models
    ----------------

    Provides model layer for weppy's dal.

    :copyright: (c) 2014-2016 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

from collections import OrderedDict
from .._compat import iteritems, with_metaclass
from .apis import computation, virtualfield, fieldmethod, scope
from .base import Field, _Field, sdict
from .helpers import HasOneWrap, HasManyWrap, HasManyViaWrap, \
    VirtualWrap, ScopeWrap, Callback, make_tablename


class MetaModel(type):
    def __new__(cls, name, bases, attrs):
        new_class = type.__new__(cls, name, bases, attrs)
        if bases == (object,):
            return new_class
        #: collect declared attributes
        tablename = attrs.get('tablename')
        current_fields = []
        current_vfields = []
        computations = {}
        callbacks = {}
        scopes = {}
        for key, value in list(attrs.items()):
            if isinstance(value, Field):
                current_fields.append((key, value))
            elif isinstance(value, virtualfield):
                current_vfields.append((key, value))
            elif isinstance(value, computation):
                computations[key] = value
            elif isinstance(value, Callback):
                callbacks[key] = value
            elif isinstance(value, scope):
                scopes[key] = value
        #: get super declared attributes
        declared_fields = OrderedDict()
        declared_vfields = OrderedDict()
        super_relations = sdict(
            _belongs_ref_=[], _refers_ref_=[],
            _hasone_ref_=[], _hasmany_ref_=[]
        )
        declared_computations = {}
        declared_callbacks = {}
        declared_scopes = {}
        for base in reversed(new_class.__mro__[1:]):
            #: collect fields from base class
            if hasattr(base, '_declared_fields_'):
                declared_fields.update(base._declared_fields_)
            #: collect relations from base class
            for key in list(super_relations):
                if hasattr(base, key):
                    super_relations[key] += getattr(base, key)
            #: collect virtuals from base class
            if hasattr(base, '_declared_virtuals_'):
                declared_vfields.update(base._declared_virtuals_)
            #: collect computations from base class
            if hasattr(base, '_declared_computations_'):
                declared_computations.update(base._declared_computations_)
            #: collect callbacks from base class
            if hasattr(base, '_declared_callbacks_'):
                declared_callbacks.update(base._declared_callbacks_)
            if hasattr(base, '_declared_scopes_'):
                declared_scopes.update(base._declared_scopes_)
        #: set tablename
        new_class._declared_tablename_ = tablename
        #: set fields with correct order
        current_fields.sort(key=lambda x: x[1]._inst_count_)
        declared_fields.update(current_fields)
        new_class._declared_fields_ = declared_fields
        #: set relations references binding
        from .apis import belongs_to, refers_to, has_one, has_many
        items = []
        for item in belongs_to._references_.values():
            items += item.reference
        new_class._belongs_ref_ = super_relations._belongs_ref_ + items
        belongs_to._references_ = {}
        items = []
        for item in refers_to._references_.values():
            items += item.reference
        new_class._refers_ref_ = super_relations._refers_ref_ + items
        refers_to._references_ = {}
        items = []
        for item in has_one._references_.values():
            items += item.reference
        new_class._hasone_ref_ = super_relations._hasone_ref_ + items
        has_one._references_ = {}
        items = []
        for item in has_many._references_.values():
            items += item.reference
        new_class._hasmany_ref_ = super_relations._hasmany_ref_ + items
        has_many._references_ = {}
        #: set virtual fields with correct order
        current_vfields.sort(key=lambda x: x[1]._inst_count_)
        declared_vfields.update(current_vfields)
        new_class._declared_virtuals_ = declared_vfields
        #: set computations
        declared_computations.update(computations)
        new_class._declared_computations_ = declared_computations
        #: set callbacks
        declared_callbacks.update(callbacks)
        new_class._declared_callbacks_ = declared_callbacks
        #: set scopes
        declared_scopes.update(scopes)
        new_class._declared_scopes_ = declared_scopes
        return new_class


class Model(with_metaclass(MetaModel)):
    db = None
    table = None

    #sign_table = False
    auto_validation = True

    validation = {}
    default_values = {}
    update_values = {}
    repr_values = {}
    form_labels = {}
    form_info = {}
    form_rw = {}
    form_widgets = {}

    @property
    def config(self):
        return self.db.config

    @classmethod
    def __getsuperprops(cls):
        superattr = "_supermodels" + cls.__name__
        if hasattr(cls, superattr):
            return
        supermodels = cls.__bases__
        superattr_val = []
        for supermodel in supermodels:
            try:
                supermodel.__getsuperprops()
                superattr_val.append(supermodel)
            except:
                pass
        setattr(cls, superattr, superattr_val)
        sup = getattr(cls, superattr)
        if not sup:
            return
        #: get super model fields' properties
        proplist = ['validation', 'default_values', 'update_values',
                    'repr_values', 'form_labels', 'form_info', 'form_rw',
                    'form_widgets']
        for prop in proplist:
            props = {}
            for model in sup:
                superprops = getattr(model, prop)
                for k, v in superprops.items():
                    props[k] = v
            for k, v in getattr(cls, prop).items():
                props[k] = v
            setattr(cls, prop, props)

    def __new__(cls):
        if cls._declared_tablename_ is None:
            cls.tablename = make_tablename(cls.__name__)
        cls.__getsuperprops()
        return super(Model, cls).__new__(cls)

    def __init__(self):
        if not hasattr(self, 'migrate'):
            self.migrate = self.config.get('migrate', self.db._migrate)
        if not hasattr(self, 'format'):
            self.format = None

    def __parse_relation_via(self, via):
        if via is None:
            return via
        rv = {'field': None}
        splitted = via.split('.')
        rv['via'] = splitted[0]
        if len(splitted) > 1:
            rv['field'] = splitted[1]
        return rv

    def __parse_belongs_relation(self, item):
        rv = {}
        if isinstance(item, dict):
            rv['name'] = list(item)[0]
            rv['model'] = item[rv['name']]
            if rv['model'] == "self":
                rv['model'] = self.__class__.__name__
        else:
            rv['name'] = item
            rv['model'] = item.capitalize()
        return rv

    def __parse_many_relation(self, item, singularize=True):
        rv = {}
        if isinstance(item, dict):
            rv['name'] = list(item)[0]
            rv['model'] = item[rv['name']]
        else:
            rv['name'] = item
            rv['model'] = item.capitalize()
            if singularize:
                rv['model'] = rv['model'][:-1]
        if isinstance(rv['model'], dict):
            if rv['model'].get('via'):
                rv.update(self.__parse_relation_via(rv['model']['via']))
                del rv['model']
        else:
            splitted = rv['model'].split('.')
            rv['model'] = splitted[0]
            if len(splitted) > 1:
                rv['field'] = splitted[1]
            else:
                rv['field'] = self.__class__.__name__.lower()
            if rv['model'] == "self":
                rv['model'] = self.__class__.__name__
        return rv

    def _define_props_(self):
        #: create pydal's Field elements
        self.fields = []
        for name, obj in iteritems(self._declared_fields_):
            if obj.modelname is not None:
                obj = Field(obj._type, *obj._args, **obj._kwargs)
                setattr(self.__class__, name, obj)
            self.fields.append(obj._make_field(name, self))

    def _define_relations_(self):
        self._virtual_relations_ = OrderedDict()
        bad_args_error = "belongs_to, has_one and has_many only accept " + \
            "strings or dicts as arguments"
        #: belongs_to and refers_to are mapped with 'reference' type Field
        _references = []
        _reference_keys = ['_belongs_ref_', '_refers_ref_']
        belongs_references = {}
        for key in _reference_keys:
            if hasattr(self, key):
                _references.append(getattr(self, key))
            else:
                _references.append([])
        isbelongs = True
        for _references_obj in _references:
            for item in _references_obj:
                if not isinstance(item, (str, dict)):
                    raise RuntimeError(bad_args_error)
                reference = self.__parse_belongs_relation(item)
                if reference['model'] != self.__class__.__name__:
                    tablename = self.db[reference['model']]._tablename
                else:
                    tablename = self.tablename
                if isbelongs:
                    fieldobj = Field('reference '+tablename)
                else:
                    fieldobj = Field(
                        'reference '+tablename, ondelete='nullify',
                        _isrefers=True)
                setattr(self.__class__, reference['name'], fieldobj)
                self.fields.append(
                    getattr(self, reference['name'])._make_field(
                        reference['name'], self)
                )
                belongs_references[reference['name']] = reference['model']
            isbelongs = False
        setattr(self.__class__, '_belongs_ref_', belongs_references)
        #delattr(self.__class__, '_refers_ref_')
        #: has_one are mapped with virtualfield()
        hasone_references = {}
        if hasattr(self, '_hasone_ref_'):
            for item in getattr(self, '_hasone_ref_'):
                if not isinstance(item, (str, dict)):
                    raise RuntimeError(bad_args_error)
                reference = self.__parse_many_relation(item, False)
                self._virtual_relations_[reference['name']] = \
                    virtualfield(reference['name'])(HasOneWrap(reference))
                hasone_references[reference['name']] = reference
        setattr(self.__class__, '_hasone_ref_', hasone_references)
        #: has_many are mapped with virtualfield()
        hasmany_references = {}
        if hasattr(self, '_hasmany_ref_'):
            for item in getattr(self, '_hasmany_ref_'):
                if not isinstance(item, (str, dict)):
                    raise RuntimeError(bad_args_error)
                reference = self.__parse_many_relation(item)
                #rclass = via = None
                #if isinstance(reference, dict):
                #    rclass = reference.get('class')
                #    via = reference.get('via')
                if reference.get('via') is not None:
                    #: maps has_many({'things': {'via': 'otherthings'}})
                    self._virtual_relations_[reference['name']] = \
                        virtualfield(reference['name'])(
                            HasManyViaWrap(reference)
                        )
                else:
                    #: maps has_many('things'),
                    #  has_many({'things': 'othername'})
                    #if rclass is not None:
                    #    reference = rclass
                    self._virtual_relations_[reference['name']] = \
                        virtualfield(reference['name'])(
                            HasManyWrap(reference)
                        )
                hasmany_references[reference['name']] = reference
        setattr(self.__class__, '_hasmany_ref_', hasmany_references)

    def _define_virtuals_(self):
        err = 'virtualfield or fieldmethod cannot have same name as an' + \
            'existent field!'
        field_names = [field.name for field in self.fields]
        for attr in ['_virtual_relations_', '_declared_virtuals_']:
            for name, obj in iteritems(getattr(self, attr, {})):
                if obj.field_name in field_names:
                    raise RuntimeError(err)
                if isinstance(obj, fieldmethod):
                    f = _Field.Method(obj.field_name, VirtualWrap(self, obj))
                else:
                    f = _Field.Virtual(obj.field_name, VirtualWrap(self, obj))
                self.fields.append(f)

    def _define_(self):
        #if self.sign_table:
        #    from .tools import Auth
        #    fakeauth = Auth(DAL(None))
        #    self.fields.extend([fakeauth.signature])
        self.__define_validation()
        self.__define_defaults()
        self.__define_updates()
        self.__define_representation()
        self.__define_computations()
        self.__define_callbacks()
        self.__define_scopes()
        self.__define_form_utils()
        self.setup()

    def __define_validation(self):
        for field in self.fields:
            if isinstance(field, (_Field.Method, _Field.Virtual)):
                continue
            validation = self.validation.get(field.name, {})
            if isinstance(validation, dict):
                for key in list(validation):
                    field._requires[key] = validation[key]
            elif isinstance(validation, list):
                field._custom_requires += validation
            else:
                field._custom_requires.append(validation)
            field._parse_validation()

    def __define_defaults(self):
        for field, value in self.default_values.items():
            self.table[field].default = value

    def __define_updates(self):
        for field, value in self.update_values.items():
            self.table[field].update = value

    def __define_representation(self):
        for field, value in self.repr_values.items():
            self.table[field].represent = value

    def __define_computations(self):
        err = 'computations should have the name of an existing field to ' +\
            'compute!'
        field_names = [field.name for field in self.fields]
        for name, obj in iteritems(self._declared_computations_):
            if obj.field_name not in field_names:
                raise RuntimeError(err)
            # TODO add check virtuals
            self.table[obj.field_name].compute = \
                lambda row, obj=obj, self=self: obj.f(self, row)

    def __define_callbacks(self):
        for name, obj in iteritems(self._declared_callbacks_):
            for t in obj.t:
                if t in ["_before_insert", "_before_delete", "_after_delete"]:
                    getattr(self.table, t).append(
                        lambda a, obj=obj, self=self: obj.f(self, a)
                    )
                else:
                    getattr(self.table, t).append(
                        lambda a, b, obj=obj, self=self: obj.f(self, a, b))

    def __define_scopes(self):
        self._scopes_ = {}
        for name, obj in iteritems(self._declared_scopes_):
            self._scopes_[obj.name] = obj
            if not hasattr(self.__class__, obj.name):
                setattr(
                    self.__class__, obj.name,
                    ScopeWrap(self.__class__.db, self, obj.f))

    def __define_form_utils(self):
        #: labels
        for field, value in self.form_labels.items():
            self.table[field].label = value
        #: info
        for field, value in self.form_info.items():
            self.table[field].comment = value
        #: rw
        try:
            self.table.is_active.writable = self.table.is_active.readable = \
                False
        except:
            pass
        for field, value in self.form_rw.items():
            if isinstance(value, (tuple, list)):
                writable, readable = value
            else:
                writable = value
                readable = value
            self.table[field].writable = writable
            self.table[field].readable = readable
        #: widgets
        for field, value in self.form_widgets.items():
            self.table[field].widget = value

    def setup(self):
        pass

    @classmethod
    def create(cls, *args, **kwargs):
        #rv = sdict(id=None)
        #vals = sdict()
        #errors = sdict()
        if args:
            if isinstance(args[0], (dict, sdict)):
                for key in list(args[0]):
                    kwargs[key] = args[0][key]
        #for field in cls.table.fields:
        #    value = kwargs.get(field)
        #    vals[field], error = cls.table[field].validate(value)
        #    if error:
        #        errors[field] = error
        #if not errors:
        #    rv.id = cls.table.insert(**vals)
        #rv.errors = errors
        #return rv
        return cls.table.validate_and_insert(**kwargs)

    @classmethod
    def validate(cls, row):
        row = sdict(row)
        errors = sdict()
        for field in cls.table.fields:
            default = getattr(cls.table[field], 'default')
            if callable(default):
                default = default()
            value = row.get(field, default)
            rv, error = cls.table[field].validate(value)
            if error:
                errors[field] = error
        return errors

    @classmethod
    def where(cls, cond):
        if not callable(cond):
            raise SyntaxError('Model.where expects a function as parameter.')
        return cls.db.where(cond(cls), model=cls.table._model_)

    @classmethod
    def all(cls):
        return cls.db(cls.table)

    @classmethod
    def first(cls):
        return cls.all().select(orderby=cls.id, limitby=(0, 1)).first()

    @classmethod
    def last(cls):
        return cls.all().select(orderby=~cls.id, limitby=(0, 1)).first()

    @classmethod
    def get(cls, *args, **kwargs):
        if len(args) == 1:
            return cls.table[args[0]]
        return cls.table(**kwargs)

    @classmethod
    def form(cls, record=None, **kwargs):
        from ..forms import DALForm
        return DALForm(cls.table, record, **kwargs)
