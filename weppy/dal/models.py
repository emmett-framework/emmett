from .apis import computation, virtualfield, fieldmethod, modelmethod
from .base import DAL, Field, _Field, sdict
from .helpers import MetaModel, HasOneWrap, HasManyWrap, HasManyViaWrap, \
    VirtualWrap, Callback, make_tablename


class Model(object):
    __metaclass__ = MetaModel

    db = None
    entity = None

    sign_table = False
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
            cls.tablename = make_tablename(cls.__name__)
        #: get super model fields' properties
        proplist = ['validation', 'default_values', 'update_values',
                    'repr_values', 'form_labels', 'form_info', 'form_rw',
                    'form_widgets']
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
            cls.tablename = make_tablename(cls.__name__)
        cls.__getsuperprops()
        return super(Model, cls).__new__(cls)

    def __init__(self):
        if not hasattr(self, 'migrate'):
            self.migrate = self.config.get('migrate', self.db._migrate)
        if not hasattr(self, 'format'):
            self.format = None

    def __parse_relation(self, item, singular=False):
        if isinstance(item, dict):
            refname = list(item)[0]
            reference = item[refname]
        else:
            reference = item.capitalize()
            refname = item
            if singular:
                reference = reference[:-1]
        return reference, refname

    def __define(self):
        if self.sign_table:
            from .tools import Auth
            fakeauth = Auth(DAL(None))
            self.fields.extend([fakeauth.signature])
        self.__define_validation()
        self.__define_defaults()
        self.__define_updates()
        self.__define_representation()
        self.__define_computations()
        self.__define_actions()
        self.__define_form_utils()
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
        belongs_references = {}
        if hasattr(self, '_belongs_ref_'):
            for item in getattr(self, '_belongs_ref_'):
                if not isinstance(item, (str, dict)):
                    raise RuntimeError(bad_args_error)
                reference, refname = self.__parse_relation(item)
                tablename = self.db[reference]._tablename
                setattr(self.__class__, refname, Field('reference '+tablename))
                self.fields.append(
                    getattr(self, refname)._make_field(refname, self)
                )
                belongs_references[reference] = refname
        setattr(self.__class__, '_belongs_ref_', belongs_references)
        #: has_one are mapped with virtualfield()
        if hasattr(self, '_hasone_ref_'):
            for item in getattr(self, '_hasone_ref_'):
                if not isinstance(item, (str, dict)):
                    raise RuntimeError(bad_args_error)
                reference, refname = self.__parse_relation(item)
                setattr(self, refname,
                        virtualfield(refname)(HasOneWrap(reference)))
            delattr(self.__class__, '_hasone_ref_')
        #: has_many are mapped with virtualfield()
        hasmany_references = {}
        if hasattr(self, '_hasmany_ref_'):
            for item in getattr(self, '_hasmany_ref_'):
                if not isinstance(item, (str, dict)):
                    raise RuntimeError(bad_args_error)
                reference, refname = self.__parse_relation(item, True)
                rclass = via = None
                if isinstance(reference, dict):
                    rclass = reference.get('class')
                    via = reference.get('via')
                if via is not None:
                    #: maps has_many({'things': {'via': 'otherthings'}})
                    setattr(
                        self, refname, virtualfield(refname)(
                            HasManyViaWrap(refname, via)
                        )
                    )
                else:
                    #: maps has_many('things'),
                    #  has_many({'things': 'othername'})
                    #  has_many({'things': {'class': 'Model'}})
                    if rclass is not None:
                        reference = rclass
                    setattr(
                        self, refname, virtualfield(refname)(
                            HasManyWrap(reference)
                        )
                    )
                hasmany_references[refname] = reference
        setattr(self.__class__, '_hasmany_ref_', hasmany_references)
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
                    f = _Field.Method(obj.field_name, VirtualWrap(self, obj))
                else:
                    f = _Field.Virtual(obj.field_name, VirtualWrap(self, obj))
                self.fields.append(f)

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
            self.entity[field].default = value

    def __define_updates(self):
        for field, value in self.update_values.items():
            self.entity[field].update = value

    def __define_representation(self):
        for field, value in self.repr_values.items():
            self.entity[field].represent = value

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

    def __define_actions(self):
        for name in dir(self):
            if not name.startswith("_"):
                obj = getattr(self, name)
                if isinstance(obj, Callback):
                    for t in obj.t:
                        if t in ["_before_insert", "_before_delete",
                                 "_after_delete"]:
                            getattr(self.entity, t).append(
                                lambda a, obj=obj, self=self: obj.f(self, a))
                        else:
                            getattr(self.entity, t).append(
                                lambda a, b, obj=obj, self=self: obj.f(
                                    self, a, b))

    def __define_form_utils(self):
        #: labels
        for field, value in self.form_labels.items():
            self.entity[field].label = value
        #: info
        for field, value in self.form_info.items():
            self.entity[field].comment = value
        #: rw
        try:
            self.entity.is_active.writable = self.entity.is_active.readable = \
                False
        except:
            pass
        for field, value in self.form_rw.items():
            if isinstance(value, (tuple, list)):
                writable, readable = value
            else:
                writable = value
                readable = value
            self.entity[field].writable = writable
            self.entity[field].readable = readable
        #: widgets
        for field, value in self.form_widgets.items():
            self.entity[field].widget = value

    def setup(self):
        pass

    #@modelmethod
    #def new(db, entity, **kwargs):
    #   return Row(**kwargs)

    @modelmethod
    def create(db, entity, *args, **kwargs):
        rv = sdict(id=None)
        vals = sdict()
        errors = sdict()
        if args:
            if isinstance(args[0], (dict, sdict)):
                for key in list(args[0]):
                    kwargs[key] = args[0][key]
        for field in entity.fields:
            value = kwargs.get(field)
            vals[field], error = entity[field].validate(value)
            if error:
                errors[field] = error
        if not errors:
            rv.id = entity.insert(**vals)
        rv.errors = errors
        return rv

    @modelmethod
    def validate(db, entity, row):
        row = sdict(row)
        errors = sdict()
        for field in entity.fields:
            value = row.get(field)
            rv, error = entity[field].validate(value)
            if error:
                errors[field] = error
        return errors

    @modelmethod
    def form(db, entity, record=None, **kwargs):
        from .forms import DALForm
        return DALForm(entity, record, **kwargs)


class AuthModel(Model):
    auth = None

    form_registration_rw = {}
    form_profile_rw = {}

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
        self.__super_method('define_validation')()
        self.__super_method('define_defaults')()
        self.__super_method('define_updates')()
        self.__super_method('define_representation')()
        self.__super_method('define_computations')()
        self.__super_method('define_actions')()
        self.__hide_all()
        self.__super_method('define_form_utils')
        self.__define_authform_utils()
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

    def __define_authform_utils(self):
        settings_map = {
            'register_fields': 'form_registration_rw',
            'profile_fields': 'form_profile_rw'
        }
        for setting, attr in settings_map.items():
            l = self.auth.settings[setting] or self.__base_visibility()
            for field, value in getattr(self, attr).items():
                show = value[1] if isinstance(value, (tuple, list)) else value
                if show:
                    #self.entity[field].writable = value[0]
                    #self.entity[field].readable = value[1]
                    l.append(field)
                else:
                    if field in l:
                        l.remove(field)
            if l:
                self.auth.settings[setting] = l
