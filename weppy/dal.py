"""
    weppy.dal
    ---------

    Provides the pyDAL implementation for weppy.

    :copyright: (c) 2015 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

import os
from pydal import DAL as _pyDAL
from pydal import Field as _Field
from weppy import serializers as _serializers
from weppy import validators as _validators
from ._compat import copyreg
from .datastructures import sdict
from .handlers import Handler
from .security import uuid as _uuid
from .validators import ValidateFromDict


def _default_validators(db, field):
    """
    Field type validation, using web2py's validators mechanism.
    makes sure the content of a field is in line with the declared
    fieldtype
    """
    requires = []
    #if field.type in (('string', 'text', 'password')):
        #requires = parser(field, {'len': {'lt': field.length}})
        #requires.append(_validators.hasLength(field.length))
    #elif field.type == 'json':
    #    requires.append(_validators.isEmptyOr(_validators.isJSON()))
    #elif field.type == 'double' or field.type == 'float':
    #    requires.append(_validators.isFloat())
    #elif field.type == 'integer':
    #    requires.append(_validators.isInt())
    #elif field.type == 'bigint':
    #    requires.append(_validators.isInt())
    #elif field.type.startswith('decimal'):
    #    requires.append(_validators.isDecimal())
    #elif field.type == 'date':
    #    requires.append(_validators.isDate())
    #elif field.type == 'time':
    #    requires.append(_validators.isTime())
    #elif field.type == 'datetime':
    #    requires.append(_validators.isDatetime())
    if db and field.type.startswith('reference') and \
            field.type.find('.') < 0 and \
            field.type[10:] in db.tables:
        referenced = db[field.type[10:]]
        if hasattr(referenced, '_format') and referenced._format:
            requires = _validators.inDb(db, referenced._id, referenced._format)
            if field.unique:
                requires._and = _validators.notInDb(db, field)
            if field.tablename == field.type[10:]:
                return _validators.isEmptyOr(requires)
            return requires
    elif db and field.type.startswith('list:reference') and \
            field.type.find('.') < 0 and \
            field.type[15:] in db.tables:
        referenced = db[field.type[15:]]
        if hasattr(referenced, '_format') and referenced._format:
            requires = _validators.inDb(db, referenced._id, referenced._format,
                                        multiple=True)
        else:
            requires = _validators.inDb(db, referenced._id, multiple=True)
        if field.unique:
            requires._and = _validators.notInDb(db, field)
        if not field.notnull:
            requires = _validators.isEmptyOr(requires)
        return requires

    if field.unique:
        requires.append(_validators.notInDb(db, field))
    sff = ['in', 'do', 'da', 'ti', 'de', 'bo']
    if field.notnull and not field.type[:2] in sff:
        requires.append(_validators.isntEmpty())
    elif not field.notnull and field.type[:2] in sff and requires:
        requires[0] = _validators.isEmptyOr(requires[0])
    return requires


class DALHandler(Handler):
    def __init__(self, db):
        self.db = db

    def on_start(self):
        self.db._adapter.reconnect()

    def on_success(self):
        self.db.commit()

    def on_failure(self):
        self.db.rollback()

    def on_end(self):
        self.db._adapter.close()


class DAL(_pyDAL):
    serializers = _serializers
    #validators_method = _default_validators
    logger = None
    uuid = lambda x: _uuid()

    @staticmethod
    def uri_from_config(config=None):
        if config is None or config.adapter is None:
            config = sdict(adapter="sqlite", host="dummy.db")
        if config.adapter == "<zombie>":
            return config.adapter
        if config.adapter == "sqlite" and config.host == "memory":
            return config.adapter+":"+config.host
        uri = config.adapter+"://"
        if config.user:
            uri = uri+config.user+":"+config.password+"@"
        uri = uri+config.host
        if config.database:
            uri += "/"+config.database
        return uri

    def __new__(cls, app, *args, **kwargs):
        config = kwargs.get('config', sdict()) or app.config.db
        uri = config.uri or DAL.uri_from_config(config)
        return super(DAL, cls).__new__(cls, uri, *args, **kwargs)

    def __init__(self, app, config=sdict(), pool_size=0, folder=None,
                 **kwargs):
        self.logger = app.log
        config = config or app.config.db
        if not config.uri:
            config.uri = self.uri_from_config(config)
        self.config = config
        #: load config data
        kwargs['check_reserved'] = config.check_reserved or \
            kwargs.get('check_reserved', None)
        kwargs['migrate'] = config.migrate or kwargs.get('migrate', True)
        kwargs['fake_migrate'] = config.fake_migrate or \
            kwargs.get('fake_migrate', False)
        kwargs['fake_migrate_all'] = config.fake_migrate_all or \
            kwargs.get('fake_migrate_all', False)
        kwargs['driver_args'] = config.driver_args or \
            kwargs.get('driver_args', None)
        kwargs['adapter_args'] = config.adapter_args or \
            kwargs.get('adapter_args', None)
        #: set directory
        folder = folder or 'databases'
        folder = os.path.join(app.root_path, folder)
        if not os.path.exists(folder):
            os.mkdir(folder)
        #: finally setup pyDAL instance
        super(DAL, self).__init__(self.config.uri, pool_size, folder, **kwargs)

    @property
    def handler(self):
        return DALHandler(self)

    def define_models(self, datamodels=[]):
        for datamodel in datamodels:
            if not hasattr(self, datamodel.__name__):
                # store actual db instance in model
                datamodel.db = self
                # init datamodel
                obj = datamodel()
                getattr(obj, '_Model__define_props')()
                getattr(obj, '_Model__define_relations')()
                getattr(obj, '_Model__define_virtuals')()
                # define table and store in model
                #datamodel.fields = obj.fields
                datamodel.entity = self.define_table(
                    obj.tablename,
                    *obj.fields,
                    **dict(migrate=obj.migrate, format=obj.format)
                )
                datamodel.id = datamodel.entity.id
                # load user's definitions
                getattr(obj, '_Model__define')()
                # set reference in db for datamodel name
                self.__setattr__(datamodel.__name__, obj.entity)


def _DAL_unpickler(db_uid):
    fake_app_obj = sdict(config=sdict(db=sdict()))
    fake_app_obj.config.db.adapter = '<zombie>'
    return DAL(fake_app_obj, db_uid=db_uid)


def _DAL_pickler(db):
    return _DAL_unpickler, (db._db_uid,)

copyreg.pickle(DAL, _DAL_pickler, _DAL_unpickler)


class Field(_Field):
    _weppy_types = {'integer': 'int', 'double': 'float', 'bigint': 'int'}
    _pydal_types = {'int': 'integer'}

    def __init__(self, type='string', *args, **kwargs):
        self._type = self._weppy_types.get(type, type)
        self.modelname = None
        self._auto_validators = True
        if 'auto_requires' in kwargs:
            self._auto_validators = kwargs['auto_requires']
            del kwargs['auto_requires']
        #: intercept requires (will be processed by `_make_field`
        self._requires = {}
        self._custom_requires = []
        if 'requires' in kwargs:
            if isinstance(kwargs['requires'], dict):
                self._requires = kwargs['requires']
            else:
                self._custom_requires = kwargs['requires']
                del kwargs['requires']
                if not isinstance(self._custom_requires, list):
                    self._custom_requires = [self._custom_requires]
        self._validation = {}
        self._vparser = ValidateFromDict()
        #: store args and kwargs for `_make_field`
        self._args = args
        self._kwargs = kwargs

    def _default_validation(self):
        rv = {}
        auto_types = [
            'int', 'float', 'decimal', 'date', 'time', 'datetime', 'json'
        ]
        if self._type in auto_types:
            rv['is'] = self._type
        if self._type in ['string', 'text', 'password']:
            rv['len'] = {'lt': self.length}
        return rv

    def _parse_validation(self):
        for key in list(self._requires):
            self._validation[key] = self._requires[key]
        self.requires = self._vparser(self, self._validation) + \
            self._custom_requires

    def _make_field(self, name, model=None):
        if model is not None:
            self.modelname = model.__class__.__name__
        #: convert field type to pyDAL ones if needed
        ftype = self._pydal_types.get(self._type, self._type)
        #: create pyDAL's Field instance
        super(Field, self).__init__(name, ftype, *self._args, **self._kwargs)
        #: add automatic validation (if requested)
        if self._auto_validators:
            auto = True
            if self.modelname:
                auto = model.default_validators
            if auto:
                self._validation = self._default_validation()
        #: validators
        if not self.modelname:
            self._parse_validation()
        return self

    def __str__(self):
        return object.__str__(self)

    def __repr__(self):
        if self.modelname and self.name:
            return "<%s property of Model %s>" % (self.name, self.modelname)
        #return "unbinded property %d" % id(self)
        return super(Field, self).__repr__()


class _reference(object):
    def __init__(self, *args):
        self.reference = [arg for arg in args]
        self.refobj[id(self)] = self

    @property
    def refobj(self):
        return {}


class belongs_to(_reference):
    _references_ = {}

    @property
    def refobj(self):
        return belongs_to._references_


class has_one(_reference):
    _references_ = {}

    @property
    def refobj(self):
        return has_one._references_


class has_many(_reference):
    _references_ = {}

    @property
    def refobj(self):
        return has_many._references_


class _hasonewrap(object):
    def __init__(self, ref, field):
        self.ref = ref
        self.field = field

    def __call__(self, model, row):
        rid = row[model.tablename].id
        return model.db(model.db[self.ref][self.field] == rid).select().first()


class _hasmanywrap(object):
    def __init__(self, ref, field):
        self.ref = ref
        self.field = field

    def __call__(self, model, row):
        rid = row[model.tablename].id
        return model.db(model.db[self.ref][self.field] == rid).select()


class computation(object):
    def __init__(self, field_name):
        self.field_name = field_name

    def __call__(self, f):
        self.f = f
        return self


class virtualfield(object):
    def __init__(self, field_name):
        self.field_name = field_name

    def __call__(self, f):
        self.f = f
        return self


class fieldmethod(virtualfield):
    pass


class _virtualwrap(object):
    def __init__(self, model, virtual):
        self.model = model
        self.virtual = virtual

    def __call__(self, row, *args, **kwargs):
        return self.virtual.f(self.model, row, *args, **kwargs)


class modelmethod(object):
    def __init__(self, f):
        self.f = f

    def __get__(self, inst, model):
        self.model = model
        return self

    def __call__(self, *args, **kwargs):
        return self.f(self.model.db, self.model.entity, *args, **kwargs)


class _ModelActionF(object):
    def __init__(self, f, t):
        self.t = []
        if isinstance(f, _ModelActionF):
            self.t += f.t
            f = f.f
        self.f = f
        self.t.append(t)

    def __call__(self):
        return None


def before_insert(f):
    return _ModelActionF(f, '_before_insert')


def after_insert(f):
    return _ModelActionF(f, '_after_insert')


def before_update(f):
    return _ModelActionF(f, '_before_update')


def after_update(f):
    return _ModelActionF(f, '_after_update')


def before_delete(f):
    return _ModelActionF(f, '_before_delete')


def after_delete(f):
    return _ModelActionF(f, '_after_delete')


class _MetaModel(type):
    def __new__(cls, name, bases, attrs):
        new_class = type.__new__(cls, name, bases, attrs)
        if bases == (object,):
            return new_class
        for item in belongs_to._references_.values():
            setattr(new_class, "_belongs_ref_", item)
        belongs_to._references_ = {}
        for item in has_one._references_.values():
            setattr(new_class, "_hasone_ref_", item)
        has_one._references_ = {}
        for item in has_many._references_.values():
            setattr(new_class, "_hasmany_ref_", item)
        has_many._references_ = {}
        return new_class


class Model(object):
    __metaclass__ = _MetaModel

    db = None
    entity = None

    sign_table = False
    default_validators = True

    #fields = []
    validators = {}
    visibility = {}
    representation = {}
    widgets = {}
    labels = {}
    comments = {}
    updates = {}

    @property
    def config(self):
        return self.db.config

    @classmethod
    def __getsuperprops(cls):
        superattr = "_supermodel" + cls.__name__
        if hasattr(cls, superattr):
            return
        supermodel = cls.__base__
        try:
            supermodel.__getsuperprops()
            setattr(cls, superattr, supermodel)
        except:
            setattr(cls, superattr, None)
        sup = getattr(cls, superattr)
        if not sup:
            return
        if cls.tablename == getattr(sup, 'tablename', None):
            cls.tablename = cls.__name__.lower()+"s"
        #: get super model fields' properties
        proplist = ['validators', 'visibility', 'representation',
                    'widgets', 'labels', 'comments', 'updates']
        for prop in proplist:
            superprops = getattr(sup, prop)
            props = {}
            for k, v in superprops.items():
                props[k] = v
            for k, v in getattr(cls, prop).items():
                props[k] = v
            setattr(cls, prop, props)

    def __new__(cls):
        if not getattr(cls, 'tablename', None):
            cls.tablename = cls.__name__.lower()+"s"
        cls.__getsuperprops()
        return super(Model, cls).__new__(cls)

    def __init__(self):
        if not hasattr(self, 'migrate'):
            self.migrate = self.config.get('migrate', self.db._migrate)
        if not hasattr(self, 'format'):
            self.format = None

    def __define(self):
        if self.sign_table:
            from .tools import Auth
            fakeauth = Auth(DAL(None))
            self.fields.extend([fakeauth.signature])
        self.__define_validators()
        self.__define_visibility()
        self.__define_representation()
        self.__define_widgets()
        self.__define_labels()
        self.__define_comments()
        self.__define_updates()
        self.__define_computations()
        self.__define_actions()
        self.setup()

    def __define_props(self):
        self.fields = []
        #: create Field elements from Prop ones
        for name in dir(self):
            if name.startswith("_"):
                continue
            obj = getattr(self, name)
            if isinstance(obj, Field):
                if obj.modelname is not None:
                    #: ensure fields are new instances on subclassing
                    obj = Field(*obj._args, **obj._kwargs)
                    setattr(self.__class__, name, obj)
                self.fields.append(obj._make_field(name, self))

    def __define_relations(self):
        bad_args_error = "belongs_to, has_one and has_many only accept " + \
            "strings or dicts as arguments"
        #: belongs_to are mapped with 'reference' type Field
        if hasattr(self, '_belongs_ref_'):
            for item in getattr(self, '_belongs_ref_').reference:
                if not isinstance(item, (str, dict)):
                    raise RuntimeError(bad_args_error)
                reference = item.capitalize()
                refname = item
                if isinstance(item, dict):
                    refname = list(item)[0]
                    reference = item[refname]
                tablename = self.db[reference]._tablename
                self.fields.append(
                    _Field(refname, 'reference '+tablename)
                )
            delattr(self.__class__, '_belongs_ref_')
        #: has_one are mapped with virtualfield()
        if hasattr(self, '_hasone_ref_'):
            for item in getattr(self, '_hasone_ref_').reference:
                if not isinstance(item, (str, dict)):
                    raise RuntimeError(bad_args_error)
                reference = item.capitalize()
                refname = item
                if isinstance(item, dict):
                    refname = list(item)[0]
                    reference = item[refname]
                sname = self.__class__.__name__.lower()
                setattr(self, refname,
                        virtualfield(refname)(_hasonewrap(reference, sname)))
            delattr(self.__class__, '_hasone_ref_')
        #: has_many are mapped with fieldmethod()
        if hasattr(self, '_hasmany_ref_'):
            for item in getattr(self, '_hasmany_ref_').reference:
                if not isinstance(item, (str, dict)):
                    raise RuntimeError(bad_args_error)
                reference = item[:-1].capitalize()
                refname = item
                if isinstance(item, dict):
                    refname = list(item)[0]
                    reference = item[refname]
                sname = self.__class__.__name__.lower()
                setattr(self, refname,
                        fieldmethod(refname)(_hasmanywrap(reference, sname)))
            delattr(self.__class__, '_hasmany_ref_')
        return

    def __define_virtuals(self):
        field_names = [field.name for field in self.fields]
        for name in dir(self):
            if name.startswith("_"):
                continue
            obj = getattr(self, name)
            if isinstance(obj, virtualfield):
                if obj.field_name in field_names:
                    raise RuntimeError(
                        'virtualfield or fieldmethod cannot have same ' +
                        'name as an existent field!')
                if isinstance(obj, fieldmethod):
                    f = _Field.Method(obj.field_name, _virtualwrap(self, obj))
                else:
                    f = _Field.Virtual(obj.field_name, _virtualwrap(self, obj))
                self.fields.append(f)

    def __define_validators(self):
        for fieldname in self.entity.fields:
            validation = self.validators.get(fieldname, {})
            if isinstance(validation, dict):
                for key in list(validation):
                    self.entity[fieldname]._requires[key] = validation[key]
            elif isinstance(validation, list):
                self.entity[fieldname]._custom_requires += validation
            else:
                self.entity[fieldname]._custom_requires.append(validation)
            self.entity[fieldname]._parse_validation()

    def __define_visibility(self):
        try:
            self.entity.is_active.writable = self.entity.is_active.readable = \
                False
        except:
            pass
        for field, value in self.visibility.items():
            self.entity[field].writable, self.entity[field].readable = value

    def __define_representation(self):
        for field, value in self.representation.items():
            self.entity[field].represent = value

    def __define_widgets(self):
        for field, value in self.widgets.items():
            self.entity[field].widget = value

    def __define_labels(self):
        for field, value in self.labels.items():
            self.entity[field].label = value

    def __define_comments(self):
        for field, value in self.comments.items():
            self.entity[field].comment = value

    def __define_computations(self):
        field_names = [field.name for field in self.fields]
        for name in dir(self):
            if not name.startswith("_"):
                obj = getattr(self, name)
                if isinstance(obj, computation):
                    if obj.field_name not in field_names:
                        raise RuntimeError(
                            'computations should have the name of an ' +
                            'existing field to compute!')
                    self.entity[obj.field_name].compute = \
                        lambda row, obj=obj, self=self: obj.f(self, row)

    def __define_updates(self):
        for field, value in self.updates.items():
            self.entity[field].update = value

    def __define_actions(self):
        for name in dir(self):
            if not name.startswith("_"):
                obj = getattr(self, name)
                if isinstance(obj, _ModelActionF):
                    for t in obj.t:
                        if t in ["_before_insert", "_before_delete",
                                 "_after_delete"]:
                            getattr(self.entity, t).append(
                                lambda a, obj=obj, self=self: obj.f(self, a))
                        else:
                            getattr(self.entity, t).append(
                                lambda a, b, obj=obj, self=self: obj.f(
                                    self, a, b))

    def setup(self):
        pass

    #@modelmethod
    #def new(db, entity, **kwargs):
    #   return Row(**kwargs)

    @modelmethod
    def create(db, entity, **kwargs):
        return entity.validate_and_insert(**kwargs)

    @modelmethod
    def validate(db, entity, row):
        errors = {}
        for field in entity.fields:
            value = row[field.name]
            rv, error = field.validate(value)
            if error:
                errors[field.name] = error
        return errors

    @modelmethod
    def form(db, entity, record=None, **kwargs):
        from .forms import DALForm
        return DALForm(entity, record, **kwargs)


class AuthModel(Model):
    auth = None

    register_visibility = {}
    profile_visibility = {}

    def __new__(cls):
        if not getattr(cls, 'tablename', None):
            cls.tablename = "auth_user"
        return super(AuthModel, cls).__new__(cls)

    def __init__(self):
        self.__super_method('define_props')()
        self.__super_method('define_relations')()
        self.__super_method('define_virtuals')()
        self.__define_extra_fields()

    def __super_method(self, name):
        return getattr(super(AuthModel, self), '_Model__'+name)

    def __define(self):
        self.__super_method('define_validators')()
        self.__hide_all()
        self.__super_method('define_visibility')()
        self.__define_register_visibility()
        self.__define_profile_visibility()
        self.__super_method('define_representation')()
        self.__super_method('define_widgets')()
        self.__super_method('define_labels')()
        self.__super_method('define_comments')()
        self.__super_method('define_updates')()
        self.__super_method('define_actions')()
        self.setup()

    def __define_extra_fields(self):
        self.auth.settings.extra_fields['auth_user'] = self.fields

    def __hide_all(self):
        alwaysvisible = ['first_name', 'last_name', 'password', 'email']
        for field in self.entity.fields:
            if field not in alwaysvisible:
                self.entity[field].writable = self.entity[field].readable = \
                    False

    def __base_visibility(self):
        return [field.name for field in self.entity
                if field.type != 'id' and field.writable]

    def __define_register_visibility(self):
        l = self.auth.settings.register_fields or self.__base_visibility()
        for field, value in self.register_visibility.items():
            if value[0]:
                #self.entity[field].writable = value[0]
                #self.entity[field].readable = value[1]
                l.append(field)
            else:
                if field in l:
                    l.remove(field)
        if l:
            self.auth.settings.register_fields = l

    def __define_profile_visibility(self):
        l = self.auth.settings.profile_fields or self.__base_visibility()
        for field, value in self.profile_visibility.items():
            if value[0]:
                #self.entity[field].writable = value[0]
                #self.entity[field].readable = value[1]
                l.append(field)
            else:
                if field in l:
                    l.remove(field)
        if l:
            self.auth.settings.profile_fields = l
