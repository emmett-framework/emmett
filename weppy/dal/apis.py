# -*- coding: utf-8 -*-
"""
    weppy.dal.apis
    --------------

    Provides apis for dal.

    :copyright: (c) 2014-2016 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

from collections import OrderedDict
from .helpers import Reference, Callback
from .._internal import warn_of_deprecation


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


#: deprecated since 0.7
class computation(compute):
    def __init__(self, field_name):
        warn_of_deprecation('computation', 'compute', stack=3)
        super(computation, self).__init__(field_name)


class rowattr(object):
    _inst_count_ = 0

    def __init__(self, field_name, bind_to_model=True):
        self.field_name = field_name
        self.inject_model = bind_to_model
        self._inst_count_ = rowattr._inst_count_
        rowattr._inst_count_ += 1

    def __call__(self, f):
        self.f = f
        return self


class rowmethod(rowattr):
    pass


#: deprecated since 0.7
class virtualfield(rowattr):
    def __init__(self, field_name, current_model_only=True):
        warn_of_deprecation('virtualfield', 'rowattr', stack=3)
        super(virtualfield, self).__init__(field_name, current_model_only)


#: deprecated since 0.7
class fieldmethod(rowmethod):
    def __init__(self, field_name, current_model_only=True):
        warn_of_deprecation('fieldmethod', 'rowmethod', stack=3)
        super(fieldmethod, self).__init__(field_name, current_model_only)


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
