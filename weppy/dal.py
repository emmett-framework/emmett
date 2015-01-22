"""
    weppy.dal
    ---------

    Provides the pyDAL implementation for weppy.

    :copyright: (c) 2015 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

import os
from pydal import DAL as _pyDAL
from pydal import Field
from weppy import serializers as _serializers
from weppy import validators as _validators
from ._compat import copyreg
from .datastructures import sdict
from .handlers import Handler
from .security import uuid as _uuid


def _default_validators(db, field):
    """
    Field type validation, using web2py's validators mechanism.
    makes sure the content of a field is in line with the declared
    fieldtype
    """

    field_type, field_length = field.type, field.length
    requires = []

    def ff(r, id):
        row = r(id)
        if not row:
            return str(id)
        elif hasattr(r, '_format') and isinstance(r._format, str):
            return r._format % row
        elif hasattr(r, '_format') and callable(r._format):
            return r._format(row)
        else:
            return str(id)

    if field_type in (('string', 'text', 'password')):
        requires.append(_validators.hasLength(field_length))
    elif field_type == 'json':
        requires.append(_validators.isEmptyOr(_validators.isJSON()))
    elif field_type == 'double' or field_type == 'float':
        requires.append(_validators.isFloatInRange(-1e100, 1e100))
    elif field_type == 'integer':
        requires.append(_validators.isIntInRange(-2**31, 2**31))
    elif field_type == 'bigint':
        requires.append(_validators.isIntInRange(-2**63, 2**63))
    elif field_type.startswith('decimal'):
        requires.append(_validators.isDecimalInRange(-10**10, 10**10))
    elif field_type == 'date':
        requires.append(_validators.isDate())
    elif field_type == 'time':
        requires.append(_validators.isTime())
    elif field_type == 'datetime':
        requires.append(_validators.isDatetime())
    elif db and field_type.startswith('reference') and \
            field_type.find('.') < 0 and \
            field_type[10:] in db.tables:
        referenced = db[field_type[10:]]

        def repr_ref(id, row=None, r=referenced, f=ff):
            return f(r, id)

        field.represent = field.represent or repr_ref
        if hasattr(referenced, '_format') and referenced._format:
            requires = _validators.inDb(db, referenced._id, referenced._format)
            if field.unique:
                requires._and = _validators.notInDb(db, field)
            if field.tablename == field_type[10:]:
                return _validators.isEmptyOr(requires)
            return requires
    elif db and field_type.startswith('list:reference') and \
            field_type.find('.') < 0 and \
            field_type[15:] in db.tables:
        referenced = db[field_type[15:]]

        def list_ref_repr(ids, row=None, r=referenced, f=ff):
            if not ids:
                return None
            from pydal.adapters import GoogleDatastoreAdapter
            refs = None
            db, id = r._db, r._id
            if isinstance(db._adapter, GoogleDatastoreAdapter):
                def count(values):
                    return db(id.belongs(values)).select(id)
                rx = range(0, len(ids), 30)
                refs = reduce(lambda a, b: a & b, [count(ids[i:i+30])
                              for i in rx])
            else:
                refs = db(id.belongs(ids)).select(id)
            return (refs and ', '.join(f(r, x.id) for x in refs) or '')

        field.represent = field.represent or list_ref_repr
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
    elif field_type.startswith('list:'):
        def repr_list(values, row=None):
            return', '.join(str(v) for v in (values or []))

        field.represent = field.represent or repr_list

    if field.unique:
        requires.append(_validators.notInDb(db, field))
    sff = ['in', 'do', 'da', 'ti', 'de', 'bo']
    if field.notnull and not field_type[:2] in sff:
        requires.append(_validators.isntEmpty())
    elif not field.notnull and field_type[:2] in sff and requires:
        requires[0] = _validators.isEmptyOr(requires[0])
    return requires


class DALHandler(Handler):
    def __init__(self, db):
        self.db = db

    def on_start(self):
        self.db._adapter.reconnect()

    def on_success(self):
        self.db.commit()
        #self.db._adapter.close()

    def on_failure(self):
        self.db.rollback()
        #self.db._adapter.close()


class DAL(_pyDAL):
    serializers = _serializers
    validators_method = _default_validators
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
                getattr(obj, '_Model__define_virtuals')()
                # define table and store in model
                datamodel.entity = self.define_table(
                    obj.tablename,
                    *obj.fields,
                    **dict(migrate=obj.migrate, format=obj.format)
                )
                # load user's definitions
                getattr(obj, '_Model__define')()
                # set reference in db for datamodel name
                self.__setattr__(datamodel.__name__, obj.entity)


def DAL_unpickler(db_uid):
    fake_app_obj = sdict(config=sdict(db=sdict()))
    fake_app_obj.config.db.adapter = '<zombie>'
    return DAL(fake_app_obj, db_uid=db_uid)


def DAL_pickler(db):
    return DAL_unpickler, (db._db_uid,)

copyreg.pickle(DAL, DAL_pickler, DAL_unpickler)


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


class modelmethod(object):
    def __init__(self, f):
        self.f = f

    def __get__(self, inst, model):
        self.model = model
        return self

    def __call__(self, *args, **kwargs):
        return self.f(self.model.db, self.model.entity, *args, **kwargs)


class ModelActionF(object):
    def __init__(self, f, t):
        self.t = []
        if isinstance(f, ModelActionF):
            self.t += f.t
            f = f.f
        self.f = f
        self.t.append(t)

    def __call__(self):
        return None


def before_insert(f):
    return ModelActionF(f, '_before_insert')


def after_insert(f):
    return ModelActionF(f, '_after_insert')


def before_update(f):
    return ModelActionF(f, '_before_update')


def after_update(f):
    return ModelActionF(f, '_after_update')


def before_delete(f):
    return ModelActionF(f, '_before_delete')


def after_delete(f):
    return ModelActionF(f, '_after_delete')


class Model(object):
    db = None
    entity = None

    sign_table = False

    fields = []
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
        if getattr(cls, superattr):
            #: get supermodel fields
            fields = [f for f in getattr(cls, superattr).fields]
            toadd = []
            for field in cls.fields:
                override = (False, 0)
                for i in range(0, len(fields)):
                    if fields[i].name == field.name:
                        override = (True, i)
                        break
                if override[0]:
                    fields[i] = field
                else:
                    toadd.append(field)
            for field in toadd:
                fields.append(field)
            cls.fields = fields
            #: get super model fields' properties
            proplist = ['validators', 'visibility', 'representation',
                        'widgets', 'labels', 'comments', 'updates']
            for prop in proplist:
                superprops = getattr(getattr(cls, superattr), prop)
                props = {}
                for k, v in superprops.items():
                    props[k] = v
                for k, v in getattr(cls, prop).items():
                    props[k] = v
                setattr(cls, prop, props)

    def __new__(cls):
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

    def __define_virtuals(self):
        field_names = [field.name for field in self.fields]
        for name in dir(self):
            if not name.startswith("_"):
                obj = self.__getattribute__(name)
                if isinstance(obj, virtualfield):
                    if obj.field_name in field_names:
                        raise RuntimeError(
                            'virtualfield or fieldmethod cannot have same ' +
                            'name as an existent field!')
                    if isinstance(obj, fieldmethod):
                        f = Field.Method(obj.field_name, lambda row, obj=obj,
                                         self=self: obj.f(self, row))
                    else:
                        f = Field.Virtual(obj.field_name, lambda row, obj=obj,
                                          self=self: obj.f(self, row))
                    self.fields.append(f)

    def __define_validators(self):
        for field, value in self.validators.items():
            self.entity[field].requires = value

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
                obj = self.__getattribute__(name)
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
                obj = self.__getattribute__(name)
                if isinstance(obj, ModelActionF):
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

    #def __init__(self, migrate=None, fake_migrate=None, signature=None):
    def __init__(self):
        #if migrate is not None:
        #    self.migrate = migrate
        #if not hasattr(self, 'migrate'):
        #    self.migrate = self.config.get('db', {}).get('migrate', True)
        self.__super_method('define_virtuals')()
        self.__define_extra_fields()
        #self.auth.define_tables(signature, self.migrate, fake_migrate)

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
            if not field in alwaysvisible:
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
