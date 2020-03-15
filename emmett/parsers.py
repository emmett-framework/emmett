# -*- coding: utf-8 -*-
"""
    emmett.parsers
    --------------

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

from functools import partial
from rapidjson import (
    DM_ISO8601, DM_NAIVE_IS_UTC,
    NM_NATIVE,
    loads as _json_loads
)


class Parsers(object):
    _registry_ = {}

    @classmethod
    def register_for(cls, target):
        def wrap(f):
            cls._registry_[target] = f
            return f
        return wrap

    @classmethod
    def get_for(cls, target):
        return cls._registry_[target]


json = partial(
    _json_loads,
    datetime_mode=DM_ISO8601 | DM_NAIVE_IS_UTC,
    number_mode=NM_NATIVE
)

Parsers.register_for('json')(json)
