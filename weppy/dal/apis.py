# -*- coding: utf-8 -*-
"""
    weppy.dal.apis
    --------------

    Provides apis for dal.

    :copyright: (c) 2015 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

from .helpers import Reference, Callback


class belongs_to(Reference):
    _references_ = {}

    @property
    def refobj(self):
        return belongs_to._references_


class has_one(Reference):
    _references_ = {}

    @property
    def refobj(self):
        return has_one._references_


class has_many(Reference):
    _references_ = {}

    @property
    def refobj(self):
        return has_many._references_


class computation(object):
    def __init__(self, field_name):
        self.field_name = field_name

    def __call__(self, f):
        self.f = f
        return self


class virtualfield(object):
    _inst_count_ = 0

    def __init__(self, field_name):
        self.field_name = field_name
        self._inst_count_ = virtualfield._inst_count_
        virtualfield._inst_count_ += 1

    def __call__(self, f):
        self.f = f
        return self


class fieldmethod(virtualfield):
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
