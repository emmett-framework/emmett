from pydal.objects import Set, LazySet


class MetaModel(type):
    def __new__(cls, name, bases, attrs):
        new_class = type.__new__(cls, name, bases, attrs)
        if bases == (object,):
            return new_class
        from .apis import belongs_to, has_one, has_many
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


class Reference(object):
    def __init__(self, *args):
        self.reference = [arg for arg in args]
        self.refobj[id(self)] = self

    @property
    def refobj(self):
        return {}


class HasOneWrap(object):
    def __init__(self, ref, field):
        self.ref = ref
        self.field = field

    def __call__(self, model, row):
        rid = row[model.tablename].id
        return model.db(model.db[self.ref][self.field] == rid).select().first()


class HasManySet(LazySet):
    def __call__(self, query=None, **kwargs):
        if query is None:
            return self.select(**kwargs)
        return LazySet.__call__(self, query, **kwargs)


class HasManyWrap(object):
    def __init__(self, ref, field):
        self.ref = ref
        self.field = field

    def __call__(self, model, row):
        rid = row[model.tablename].id
        return HasManySet(model.db[self.ref][self.field], rid)


class HasManyViaSet(Set):
    def __init__(self, db, query, rfield, **kwargs):
        self._rfield = rfield
        Set.__init__(self, db, query, **kwargs)

    def __call__(self, query=None, **kwargs):
        if query is None:
            return self.select(self._rfield, **kwargs)
        return Set.__call__(self, query, **kwargs)


class HasManyViaWrap(object):
    def __init__(self, ref, via):
        self.ref = ref
        self.via = via

    def __call__(self, model, row):
        rid = row[model.tablename].id
        via = getattr(model.entity, self.via).f.virtual.f
        third = model.db[via.ref][self.ref].type.split(" ")[1]
        return HasManyViaSet(
            model.db,
            (model.db[via.ref][via.field] == rid) &
            (model.db[via.ref][self.ref] == model.db[third].id),
            model.db[third].ALL
        )


class VirtualWrap(object):
    def __init__(self, model, virtual):
        self.model = model
        self.virtual = virtual

    def __call__(self, row, *args, **kwargs):
        return self.virtual.f(self.model, row, *args, **kwargs)


class Callback(object):
    def __init__(self, f, t):
        self.t = []
        if isinstance(f, Callback):
            self.t += f.t
            f = f.f
        self.f = f
        self.t.append(t)

    def __call__(self):
        return None


"""
def _default_validators(db, field):
    requires = []
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
"""
