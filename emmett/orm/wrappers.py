# -*- coding: utf-8 -*-
"""
    emmett.orm.wrappers
    -------------------

    Provides ORM wrappers utilities.

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

from .helpers import RelationBuilder
from .objects import HasOneSet, HasOneViaSet, HasManySet, HasManyViaSet


class Wrapper(object):
    def __init__(self, ref):
        self.__name__ = ref.name
        self.ref = ref


class HasOneWrap(Wrapper):
    def __call__(self, model, row):
        return HasOneSet(model.db, RelationBuilder(self.ref, model), row)


class HasOneViaWrap(Wrapper):
    def __call__(self, model, row):
        return HasOneViaSet(model.db, RelationBuilder(self.ref, model), row)


class HasManyWrap(Wrapper):
    def __call__(self, model, row):
        return HasManySet(model.db, RelationBuilder(self.ref, model), row)


class HasManyViaWrap(Wrapper):
    def __call__(self, model, row):
        return HasManyViaSet(model.db, RelationBuilder(self.ref, model), row)
