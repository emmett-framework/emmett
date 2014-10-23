"""
    weppy.dal.models
    ----------------

    Provides a models layer upon the web2py's DAL.

    :copyright: (c) 2014 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

from .base import DAL, Field
from ..tools import Auth


class ModelsDAL(DAL):
    def __init__(self, app, datamodels=None):
        self._LAZY_TABLES = dict()
        self._tables = dict()
        self.config = app.config.db
        DAL.__init__(self, app)
        self.define_datamodels(datamodels or [])

    def define_datamodels(self, datamodels):
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
    """Base Model Class
    all define_ methods will be called, then
    all set_ methods will be called."""
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

    def __init__(self, migrate=None, Format=None):
        if migrate is not None:
            self.migrate = migrate
        if not hasattr(self, 'migrate'):
            self.migrate = self.config.get('db', {}).get('migrate', True)
        if Format is not None or not hasattr(self, 'format'):
            self.format = Format

    def __define(self):
        if self.sign_table:
            fakeauth = Auth(DAL(None))
            self.fields.extend([fakeauth.signature])
        self.__define_validators()
        self.__define_visibility()
        self.__define_representation()
        self.__define_widgets()
        self.__define_labels()
        self.__define_comments()
        self.__define_updates()
        self.__define_actions()
        self.__set()

    def __set(self):
        self.set_table()
        self.set_validators()
        self.set_visibility()
        self.set_representation()
        self.set_widgets()
        self.set_labels()
        self.set_comments()
        self.set_updates()

    def __define_virtuals(self):
        fields = [field.name for field in self.fields]
        for name in dir(self):
            if not name.startswith("_"):
                obj = self.__getattribute__(name)
                if isinstance(obj, virtualfield):
                    if obj.field_name in fields:
                        raise RuntimeError('virtualfield or fieldmethod cannot have same name as an existent field!')
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
        for name in dir(self):
            if not name.startswith("_"):
                obj = self.__getattribute__(name)
                if isinstance(obj, computation):
                    if obj.field_name not in self.entity.fields:
                        raise RuntimeError('computations should have the name of an existing field to compute!')
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
                        if t in ["_before_insert", "_before_delete", "_after_delete"]:
                            getattr(self.entity, t).append(
                                lambda a, obj=obj, self=self: obj.f(self, a))
                        else:
                            getattr(self.entity, t).append(
                                lambda a, b, obj=obj, self=self: obj.f(
                                    self, a, b))

    def set_table(self):
        pass

    def set_validators(self):
        pass

    def set_visibility(self):
        pass

    def set_representation(self):
        pass

    def set_widgets(self):
        pass

    def set_labels(self):
        pass

    def set_comments(self):
        pass

    def set_updates(self):
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
        from ..forms import DALForm
        return DALForm(entity, record, **kwargs)


class AuthModel(Model):
    auth = None

    register_visibility = {}
    profile_visibility = {}

    def __init__(self, migrate=None):
        if migrate is not None:
            self.migrate = migrate
        if not hasattr(self, 'migrate'):
            self.migrate = self.config.get('db', {}).get('migrate', True)
        self.__super_method('define_virtuals')()
        self.__define_extra_fields()
        self.auth.define_tables(migrate=self.migrate)

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
        self.__set()

    def __set(self):
        self.__super_method('set')()

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
