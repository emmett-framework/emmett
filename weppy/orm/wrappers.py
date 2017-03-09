# -*- coding: utf-8 -*-
"""
    weppy.orm.wrappers
    ------------------

    Provides wrappers utilities for dal.

    :copyright: (c) 2014-2017 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

from .helpers import RelationBuilder
from .objects import HasOneSet, HasManySet, HasManyViaSet


class Wrapper(object):
    def __init__(self, ref):
        self.__name__ = ref.name
        self.ref = ref


class HasOneWrap(Wrapper):
    def __call__(self, model, row):
        return HasOneSet(model.db, RelationBuilder(self.ref, model), row)


class HasManyWrap(Wrapper):
    def __call__(self, model, row):
        return HasManySet(model.db, RelationBuilder(self.ref, model), row)


class HasManyViaWrap(Wrapper):
    def __call__(self, model, row):
        return HasManyViaSet(model.db, RelationBuilder(self.ref, model), row)
