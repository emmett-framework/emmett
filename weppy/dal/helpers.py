# -*- coding: utf-8 -*-
"""
    weppy.dal.helpers
    -----------------

    Provides helpers for dal.

    :copyright: (c) 2015 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

import re
from pydal.objects import Set, LazySet
from .._compat import iteritems


class Reference(object):
    def __init__(self, *args):
        self.reference = [arg for arg in args]
        self.refobj[id(self)] = self

    @property
    def refobj(self):
        return {}


class HasOneWrap(object):
    def __init__(self, ref):
        self.ref = ref

    def __call__(self, model, row):
        rid = row[model.tablename].id
        sname = model.__class__.__name__
        field = model.db[self.ref]._model_._belongs_ref_[sname]
        return model.db(model.db[self.ref][field] == rid).select().first()


class HasManySet(LazySet):
    def __call__(self, *args, **kwargs):
        return self.select(*args, **kwargs)

    def add(self, **data):
        rv = None
        data[self.fieldname] = self.id
        errors = self.db[self.tablename]._model_.validate(data)
        if not errors:
            rv = self.db[self.tablename].insert(**data)
        return rv, errors


class HasManyWrap(object):
    def __init__(self, ref):
        self.ref = ref

    def __call__(self, model, row):
        rid = row[model.tablename].id
        sname = model.__class__.__name__
        field = model.db[self.ref]._model_._belongs_ref_[sname]
        return HasManySet(model.db[self.ref][field], rid)


class HasManyViaSet(Set):
    def __init__(self, db, query, rfield, model, rid, via, **kwargs):
        self._rfield = rfield
        self._model = model
        self._rid = rid
        self._via = via
        Set.__init__(self, db, query, **kwargs)

    def __call__(self, *args, **kwargs):
        if not args:
            args = [self._rfield]
        return self.select(*args, **kwargs)

    def add(self, obj, **kwargs):
        # works for 3 tables way only!
        nrow = kwargs
        rv = None
        #: get belongs reference of current model
        self_field = self.db[self._via]._model_._belongs_ref_[self._model]
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


class HasManyViaWrap(object):
    def __init__(self, ref, via):
        self.ref = ref
        self.via = via

    def _get_belongs(self, db, model, value):
        for key, val in iteritems(db[model]._model_._belongs_ref_):
            if val == value:
                return key
        return None

    def __call__(self, model, row):
        db = model.db
        rid = row[model.tablename].id
        sname = model.__class__.__name__
        stack = []
        vianame = self.via
        via = model._hasmany_ref_[self.via]
        stack.append((self.ref, self.via))
        while isinstance(via, dict):
            stack.insert(0, (vianame, via['via']))
            vianame = via['via']
            via = model._hasmany_ref_[vianame]
        via_field = db[via]._model_._belongs_ref_[sname]
        query = (db[via][via_field] == rid)
        sel_field = db[via].ALL
        step_model = via
        lbelongs = None
        for vianame, viaby in stack:
            belongs = self._get_belongs(db, step_model, vianame[:-1])
            if belongs:
                #: 3 tables way
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
        return HasManyViaSet(db, query, sel_field, sname, rid, lbelongs)


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


def make_tablename(classname):
    words = re.findall('[A-Z][^A-Z]*', classname)
    tablename = '_'.join(words)
    return tablename.lower()+"s"
