# -*- coding: utf-8 -*-
"""
    weppy.dal.helpers
    -----------------

    Provides helpers for dal.

    :copyright: (c) 2015 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

import re
from .base import Set, LazySet


class Reference(object):
    def __init__(self, *args):
        self.reference = [arg for arg in args]
        self.refobj[id(self)] = self

    @property
    def refobj(self):
        return {}


class RelationBuilder(object):
    def __init__(self, ref, model):
        self.ref = ref
        self.model = model

    def _make_refid(self, row):
        if row is None:
            return self.model.id
        return row[self.model.tablename].id

    def _many_elements(self, row):
        rid = self._make_refid(row)
        sname = self.model.__class__.__name__
        fieldname = self.model.db[self.ref]._model_._belongs_ref_[sname]
        field = self.model.db[self.ref][fieldname]
        return field, rid

    def _get_belongs(self, modelname, value):
        return self.model.db[modelname]._model_._belongs_map_.get(value)

    def belongs_query(self):
        return (self.model.table[self.ref[1]] == self.model.db[self.ref[0]].id)

    def many_query(self, row=None):
        field, rid = self._many_elements(row)
        return (field == rid)

    def many(self, row=None):
        return self._many_elements(row)

    def via(self, registered_via, row=None):
        db = self.model.db
        rid = self._make_refid(row)
        sname = self.model.__class__.__name__
        stack = []
        vianame = registered_via
        via = self.model._hasmany_ref_[registered_via]
        stack.append((self.ref, registered_via))
        while isinstance(via, dict):
            stack.insert(0, (vianame, via['via']))
            vianame = via['via']
            via = self.model._hasmany_ref_[vianame]
        via_field = db[via]._model_._belongs_ref_[sname]
        query = (db[via][via_field] == rid)
        sel_field = db[via].ALL
        step_model = via
        lbelongs = None
        for vianame, viaby in stack:
            belongs = self._get_belongs(step_model, vianame[:-1])
            if belongs:
                #: join table way
                lbelongs = step_model
                _query = (db[step_model][vianame[:-1]] == db[belongs].id)
                sel_field = db[belongs].ALL
                step_model = belongs
            else:
                #: shortcut mode
                many = db[step_model]._model_._hasmany_ref_[vianame]
                _query = (db[step_model].id == db[many][viaby[:-1]])
                sel_field = db[many].ALL
                step_model = many
            query = query & _query
        return query, sel_field, sname, rid, lbelongs


class HasOneWrap(object):
    def __init__(self, ref):
        self.ref = ref

    def __call__(self, model, row):
        return model.db(
            RelationBuilder(self.ref, model).many_query(row)).select().first()


class HasManySet(LazySet):
    def __call__(self, *args, **kwargs):
        return self.select(*args, **kwargs)

    def add(self, **data):
        rv = None
        data[self.fieldname] = self.id
        errors = self._model_.validate(data)
        if not errors:
            rv = self.db[self.tablename].insert(**data)
        return rv, errors

    def remove(self, obj):
        return self.db(self.db[self.tablename].id == obj.id).delete()


class HasManyWrap(object):
    def __init__(self, ref):
        self.ref = ref

    def __call__(self, model, row):
        return HasManySet(*RelationBuilder(self.ref, model).many(row))


class HasManyViaSet(Set):
    def __init__(self, db, query, rfield, modelname, rid, via, **kwargs):
        self._rfield = rfield
        self._modelname = modelname
        self._rid = rid
        self._via = via
        super(HasManyViaSet, self).__init__(
            db, query, model=db[modelname]._model_, **kwargs)
        self._via_error = \
            'Cannot %s elements to an has_many relation without a join table'

    def __call__(self, *args, **kwargs):
        if not args:
            args = [self._rfield]
        return self.select(*args, **kwargs)

    def add(self, obj, **kwargs):
        # works on join tables only!
        if self._via is None:
            raise RuntimeError(self._via_error % 'add')
        nrow = kwargs
        rv = None
        #: get belongs reference of current model
        self_field = self.db[self._via]._model_._belongs_ref_[self._modelname]
        #: get other model belongs data
        other_model = self._rfield._table._model_.__class__.__name__
        other_field = self.db[self._via]._model_._belongs_ref_[other_model]
        nrow[self_field] = self._rid
        nrow[other_field] = obj.id
        #: validate and insert
        errors = self.db[self._via]._model_.validate(nrow)
        if not errors:
            rv = self.db[self._via].insert(**nrow)
        return rv, errors

    def remove(self, obj):
        # works on join tables only!
        if self._via is None:
            raise RuntimeError(self._via_error % 'remove')
        #: get belongs reference of current model
        self_field = self.db[self._via]._model_._belongs_ref_[self._modelname]
        #: get other model belongs data
        other_model = self._rfield._table._model_.__class__.__name__
        other_field = self.db[self._via]._model_._belongs_ref_[other_model]
        #: delete
        return self.db(
            (self.db[self._via][self_field] == self._rid) &
            (self.db[self._via][other_field] == obj.id)).delete()


class HasManyViaWrap(object):
    def __init__(self, ref, via):
        self.ref = ref
        self.via = via

    def __call__(self, model, row):
        return HasManyViaSet(
            model.db, *RelationBuilder(self.ref, model).via(self.via, row))


class VirtualWrap(object):
    def __init__(self, model, virtual):
        self.model = model
        self.virtual = virtual

    def __call__(self, row, *args, **kwargs):
        return self.virtual.f(self.model, row, *args, **kwargs)


class ScopeWrap(object):
    def __init__(self, set, model, scope):
        self.set = set
        self.model = model
        self.scope = scope

    def __call__(self, *args, **kwargs):
        return self.set.where(self.scope(self.model, *args, **kwargs))


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


def make_tablename(classname):
    words = re.findall('[A-Z][^A-Z]*', classname)
    tablename = '_'.join(words)
    return tablename.lower()+"s"
