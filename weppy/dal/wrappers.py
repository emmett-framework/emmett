# -*- coding: utf-8 -*-
"""
    weppy.dal.wrappers
    ------------------

    Provides wrappers utilities for dal.

    :copyright: (c) 2014-2016 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

from .helpers import RelationBuilder
from .objects import HasOneSet, HasManySet, HasManyViaSet


class HasOneWrap(object):
    def __init__(self, ref):
        self.ref = ref

    def __call__(self, model, row):
        return HasOneSet(model.db, RelationBuilder(self.ref, model), row)


class HasManyWrap(object):
    def __init__(self, ref):
        self.ref = ref

    def __call__(self, model, row):
        return HasManySet(model.db, RelationBuilder(self.ref, model), row)


class HasManyViaWrap(object):
    def __init__(self, ref):
        self.ref = ref

    def __call__(self, model, row):
        return HasManyViaSet(model.db, RelationBuilder(self.ref, model), row)


class VirtualWrap(object):
    def __init__(self, model, virtual):
        self.model = model
        self.virtual = virtual
        if self.virtual.inject_model:
            self.call = self._inject_call
        else:
            self.call = self._call

    def _inject_call(self, row, *args, **kwargs):
        return self._call(row[self.model.tablename], *args, **kwargs)

    def _call(self, row, *args, **kwargs):
        return self.virtual.f(self.model, row, *args, **kwargs)

    def __call__(self, row, *args, **kwargs):
        return self.call(row, *args, **kwargs)
