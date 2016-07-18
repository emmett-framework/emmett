# -*- coding: utf-8 -*-
"""
    weppy.dal.models
    ----------------

    Provides model layer for weppy's dal.

    :copyright: (c) 2014-2016 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

from collections import OrderedDict
from pydal.objects import Row
from .._compat import iteritems, itervalues, with_metaclass
from .apis import compute, rowattr, rowmethod, scope
from .base import Field, _Field, sdict
from .helpers import HasOneWrap, HasManyWrap, HasManyViaWrap, \
    VirtualWrap, ScopeWrap, Callback, ReferenceData, make_tablename


class MetaModel(type):
    def __new__(cls, name, bases, attrs):
        new_class = type.__new__(cls, name, bases, attrs)
        if bases == (object,):
            return new_class
        #: collect declared attributes
        tablename = attrs.get('tablename')
        fields = []
        vfields = []
        computations = []
        callbacks = []
        declared_fields = OrderedDict()
        declared_vfields = OrderedDict()
        declared_computations = OrderedDict()
        declared_callbacks = OrderedDict()
        declared_scopes = {}
        for key, value in list(attrs.items()):
            if isinstance(value, Field):
                fields.append((key, value))
            elif isinstance(value, rowattr):
                vfields.append((key, value))
            elif isinstance(value, compute):
                computations.append((key, value))
            elif isinstance(value, Callback):
                callbacks.append((key, value))
            elif isinstance(value, scope):
                declared_scopes[key] = value
        declared_relations = sdict(
            belongs=OrderedDict(), refers=OrderedDict(),
            hasone=OrderedDict(), hasmany=OrderedDict()
        )
        from .apis import belongs_to, refers_to, has_one, has_many
        for ref in belongs_to._references_.values():
            for item in ref.reference:
                rkey = list(item)[0] if isinstance(item, dict) else item
                declared_relations.belongs[rkey] = item
        belongs_to._references_ = {}
        for ref in refers_to._references_.values():
            for item in ref.reference:
                rkey = list(item)[0] if isinstance(item, dict) else item
                declared_relations.refers[rkey] = item
        refers_to._references_ = {}
        for ref in has_one._references_.values():
            for item in ref.reference:
                rkey = list(item)[0] if isinstance(item, dict) else item
                declared_relations.hasone[rkey] = item
        has_one._references_ = {}
        for ref in has_many._references_.values():
            for item in ref.reference:
                rkey = list(item)[0] if isinstance(item, dict) else item
                declared_relations.hasmany[rkey] = item
        has_many._references_ = {}
        #: sort declared attributes that keeps order
        fields.sort(key=lambda x: x[1]._inst_count_)
        vfields.sort(key=lambda x: x[1]._inst_count_)
        computations.sort(key=lambda x: x[1]._inst_count_)
        callbacks.sort(key=lambda x: x[1]._inst_count_)
        declared_fields.update(fields)
        declared_vfields.update(vfields)
        declared_computations.update(computations)
        declared_callbacks.update(callbacks)
        #: store declared attributes in class
        new_class._declared_tablename_ = tablename
        new_class._declared_fields_ = declared_fields
        new_class._declared_virtuals_ = declared_vfields
        new_class._declared_computations_ = declared_computations
        new_class._declared_callbacks_ = declared_callbacks
        new_class._declared_scopes_ = declared_scopes
        new_class._declared_belongs_ref_ = declared_relations.belongs
        new_class._declared_refers_ref_ = declared_relations.refers
        new_class._declared_hasone_ref_ = declared_relations.hasone
        new_class._declared_hasmany_ref_ = declared_relations.hasmany
        #: get super declared attributes
        all_fields = OrderedDict()
        all_vfields = OrderedDict()
        all_computations = OrderedDict()
        all_callbacks = OrderedDict()
        all_scopes = {}
        all_relations = sdict(
            belongs=OrderedDict(), refers=OrderedDict(),
            hasone=OrderedDict(), hasmany=OrderedDict()
        )
        for base in reversed(new_class.__mro__[1:]):
            if hasattr(base, '_declared_fields_'):
                all_fields.update(base._declared_fields_)
            if hasattr(base, '_declared_virtuals_'):
                all_vfields.update(base._declared_virtuals_)
            if hasattr(base, '_declared_computations_'):
                all_computations.update(base._declared_computations_)
            if hasattr(base, '_declared_callbacks_'):
                all_callbacks.update(base._declared_callbacks_)
            if hasattr(base, '_declared_scopes_'):
                all_scopes.update(base._declared_scopes_)
            for key in list(all_relations):
                attrkey = '_declared_' + key + '_ref_'
                if hasattr(base, attrkey):
                    all_relations[key].update(getattr(base, attrkey))
        #: compose 'all' attributes
        all_fields.update(declared_fields)
        all_vfields.update(declared_vfields)
        all_computations.update(declared_computations)
        all_callbacks.update(declared_callbacks)
        all_scopes.update(declared_scopes)
        for key in list(all_relations):
            all_relations[key].update(declared_relations[key])
        #: store 'all' attributes on class
        new_class._all_fields_ = all_fields
        new_class._all_virtuals_ = all_vfields
        new_class._all_computations_ = all_computations
        new_class._all_callbacks_ = all_callbacks
        new_class._all_scopes_ = all_scopes
        new_class._all_belongs_ref_ = all_relations.belongs
        new_class._all_refers_ref_ = all_relations.refers
        new_class._all_hasone_ref_ = all_relations.hasone
        new_class._all_hasmany_ref_ = all_relations.hasmany
        return new_class


class Model(with_metaclass(MetaModel)):
    db = None
    table = None

    #sign_table = False
    auto_validation = True

    validation = {}
    default_values = {}
    update_values = {}
    indexes = {}
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
        proplist = [
            'validation', 'default_values', 'update_values', 'indexes',
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
        rv = sdict()
        splitted = via.split('.')
        rv.via = splitted[0]
        if len(splitted) > 1:
            rv.field = splitted[1]
        return rv

    def __parse_belongs_relation(self, item):
        rv = sdict()
        if isinstance(item, dict):
            rv.name = list(item)[0]
            rv.model = item[rv.name]
            if rv.model == "self":
                rv.model = self.__class__.__name__
        else:
            rv.name = item
            rv.model = item.capitalize()
        return rv

    def __build_relation_modelname(self, name, relation, singularize):
        relation.model = name.capitalize()
        if singularize:
            relation.model = relation.model[:-1]

    def __build_relation_fieldname(self, relation):
        splitted = relation.model.split('.')
        relation.model = splitted[0]
        if len(splitted) > 1:
            relation.field = splitted[1]
        else:
            relation.field = self.__class__.__name__.lower()

    def __parse_relation_dict(self, rel, singularize):
        if 'scope' in rel.model:
            rel.scope = rel.model['scope']
        if 'where' in rel.model:
            rel.where = rel.model['where']
        if 'via' in rel.model:
            rel.update(self.__parse_relation_via(rel.model['via']))
            del rel.model
        else:
            if 'target' in rel.model:
                rel.model = rel.model['target']
            if not isinstance(rel.model, str):
                self.__build_relation_modelname(rel.name, rel, singularize)

    def __parse_many_relation(self, item, singularize=True):
        rv = ReferenceData(self)
        if isinstance(item, dict):
            rv.name = list(item)[0]
            rv.model = item[rv.name]
            if isinstance(rv.model, dict):
                if 'method' in rv.model:
                    rv.field = rv.model.get(
                        'field', self.__class__.__name__.lower())
                    rv.method = rv.model['method']
                    del rv.model
                else:
                    self.__parse_relation_dict(rv, singularize)
        else:
            rv.name = item
            self.__build_relation_modelname(item, rv, singularize)
        if rv.model:
            if not rv.field:
                self.__build_relation_fieldname(rv)
            if rv.model == "self":
                rv.model = self.__class__.__name__
        return rv

    def _define_props_(self):
        #: create pydal's Field elements
        self.fields = []
        for name, obj in iteritems(self._all_fields_):
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
        _reference_keys = ['_all_belongs_ref_', '_all_refers_ref_']
        belongs_references = {}
        for key in _reference_keys:
            if hasattr(self, key):
                _references.append(list(getattr(self, key).values()))
            else:
                _references.append([])
        isbelongs = True
        for _references_obj in _references:
            for item in _references_obj:
                if not isinstance(item, (str, dict)):
                    raise RuntimeError(bad_args_error)
                reference = self.__parse_belongs_relation(item)
                if reference.model != self.__class__.__name__:
                    tablename = self.db[reference.model]._tablename
                else:
                    tablename = self.tablename
                if isbelongs:
                    fieldobj = Field('reference ' + tablename)
                else:
                    fieldobj = Field(
                        'reference ' + tablename, ondelete='nullify',
                        _isrefers=True)
                setattr(self.__class__, reference.name, fieldobj)
                self.fields.append(
                    getattr(self, reference.name)._make_field(
                        reference.name, self)
                )
                belongs_references[reference.name] = reference.model
            isbelongs = False
        setattr(self.__class__, '_belongs_ref_', belongs_references)
        #: has_one are mapped with rowattr
        hasone_references = {}
        if hasattr(self, '_all_hasone_ref_'):
            for item in itervalues(getattr(self, '_all_hasone_ref_')):
                if not isinstance(item, (str, dict)):
                    raise RuntimeError(bad_args_error)
                reference = self.__parse_many_relation(item, False)
                self._virtual_relations_[reference.name] = \
                    rowattr(reference.name)(HasOneWrap(reference))
                hasone_references[reference.name] = reference
        setattr(self.__class__, '_hasone_ref_', hasone_references)
        #: has_many are mapped with rowattr
        hasmany_references = {}
        if hasattr(self, '_all_hasmany_ref_'):
            for item in itervalues(getattr(self, '_all_hasmany_ref_')):
                if not isinstance(item, (str, dict)):
                    raise RuntimeError(bad_args_error)
                reference = self.__parse_many_relation(item)
                if reference.via is not None:
                    #: maps has_many({'things': {'via': 'otherthings'}})
                    wrapper = HasManyViaWrap
                else:
                    #: maps has_many('things'),
                    #  has_many({'things': 'othername'})
                    wrapper = HasManyWrap
                self._virtual_relations_[reference.name] = \
                    rowattr(reference.name)(wrapper(reference))
                hasmany_references[reference.name] = reference
        setattr(self.__class__, '_hasmany_ref_', hasmany_references)

    def _define_virtuals_(self):
        err = 'rowattr or rowmethod cannot have the name of an' + \
            'existent field!'
        field_names = [field.name for field in self.fields]
        for attr in ['_virtual_relations_', '_all_virtuals_']:
            for name, obj in iteritems(getattr(self, attr, {})):
                if obj.field_name in field_names:
                    raise RuntimeError(err)
                if isinstance(obj, rowmethod):
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
        self.__define_indexes()
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
        for name, obj in iteritems(self._all_computations_):
            if obj.field_name not in field_names:
                raise RuntimeError(err)
            # TODO add check virtuals
            self.table[obj.field_name].compute = \
                lambda row, obj=obj, self=self: obj.f(self, row)

    def __define_callbacks(self):
        for name, obj in iteritems(self._all_callbacks_):
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
        for name, obj in iteritems(self._all_scopes_):
            self._scopes_[obj.name] = obj
            if not hasattr(self.__class__, obj.name):
                setattr(
                    self.__class__, obj.name,
                    ScopeWrap(self.__class__.db, self, obj.f))

    def __prepend_table_on_index_name(self, name):
        return '%s_widx__%s' % (self.tablename, name)

    def __create_index_name(self, *values):
        components = []
        for value in values:
            components.append(value.replace('_', ''))
        return self.__prepend_table_on_index_name("_".join(components))

    def __parse_index_dict(self, value):
        rv = {}
        fields = value.get('fields') or []
        if not isinstance(fields, (list, tuple)):
            fields = [fields]
        rv['fields'] = fields
        where_query = None
        where_cond = value.get('where')
        if callable(where_cond):
            where_query = where_cond(self.__class__)
        if where_query:
            rv['where'] = where_query
        expressions = []
        expressions_cond = value.get('expressions')
        if callable(expressions_cond):
            expressions = expressions_cond(self.__class__)
        if not isinstance(expressions, (tuple, list)):
            expressions = [expressions]
        rv['expressions'] = expressions
        rv['unique'] = value.get('unique', False)
        return rv

    def __define_indexes(self):
        self._indexes_ = {}
        for key, value in iteritems(self.indexes):
            if isinstance(value, bool):
                if not value:
                    continue
                if not isinstance(key, tuple):
                    key = [key]
                if any(field not in self.table for field in key):
                    raise SyntaxError(
                        'Invalid field specified in indexes: %s' % str(key))
                idx_name = self.__create_index_name(*key)
                idx_dict = {'fields': key, 'expressions': [], 'unique': False}
            elif isinstance(value, dict):
                idx_name = self.__prepend_table_on_index_name(key)
                idx_dict = self.__parse_index_dict(value)
            else:
                raise SyntaxError(
                    'Values in indexes dict should be booleans or dicts')
            self._indexes_[idx_name] = idx_dict

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
    def _inject_virtuals_on_row(cls, row):
        virtualrow = sdict({cls.tablename: row})
        for virtual in cls.table._virtual_fields:
            try:
                row[virtual.name] = virtual.f(virtualrow)
            except (AttributeError, KeyError):
                pass
        for virtualmethod in cls.table._virtual_methods:
            try:
                row[virtualmethod.name] = virtualmethod.handler(
                    virtualmethod.f, virtualrow)
            except (AttributeError, KeyError):
                pass
        return row

    @classmethod
    def new(cls, **attributes):
        row = Row()
        for field in cls.table.fields:
            val = attributes.get(field, cls.table[field].default)
            if callable(val):
                val = val()
            row[field] = val
        cls._inject_virtuals_on_row(row)
        return row

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

    @rowmethod('update_record')
    def _update_record(self, row, **fields):
        newfields = fields or dict(row)
        for fieldname in list(newfields.keys()):
            if fieldname not in self.table.fields or \
               self.table[fieldname].type == 'id':
                del newfields[fieldname]
        self.db(self.table._id == row.id, ignore_common_filters=True).update(
            **newfields
        )
        row.update(newfields)
        return row

    @rowmethod('delete_record')
    def _delete_record(self, row):
        return self.db(self.db[self.tablename]._id == row.id).delete()
