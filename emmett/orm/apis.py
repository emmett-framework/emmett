# -*- coding: utf-8 -*-
"""
    emmett.orm.apis
    ---------------

    Provides ORM apis.

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

from collections import OrderedDict
from .helpers import Reference, Callback


class belongs_to(Reference):
    _references_ = OrderedDict()

    @property
    def refobj(self):
        return belongs_to._references_


class refers_to(Reference):
    _references_ = OrderedDict()

    @property
    def refobj(self):
        return refers_to._references_


class has_one(Reference):
    _references_ = OrderedDict()

    @property
    def refobj(self):
        return has_one._references_


class has_many(Reference):
    _references_ = OrderedDict()

    @property
    def refobj(self):
        return has_many._references_


class compute(object):
    _inst_count_ = 0

    def __init__(self, field_name):
        self.field_name = field_name
        self._inst_count_ = compute._inst_count_
        compute._inst_count_ += 1

    def __call__(self, f):
        self.f = f
        return self


class rowattr(object):
    _inst_count_ = 0

    def __init__(self, field_name):
        self.field_name = field_name
        self._inst_count_ = rowattr._inst_count_
        rowattr._inst_count_ += 1

    def __call__(self, f):
        self.f = f
        return self


class rowmethod(rowattr):
    pass


def before_insert(f):
    return Callback(f, '_before_insert')


def after_insert(f):
    return Callback(f, '_after_insert')


def before_update(f):
    return Callback(f, '_before_update')


def after_update(f):
    return Callback(f, '_after_update')


def before_delete(f):
    return Callback(f, '_before_delete')


def after_delete(f):
    return Callback(f, '_after_delete')


class scope(object):
    def __init__(self, name):
        self.name = name

    def __call__(self, f):
        self.f = f
        return self
