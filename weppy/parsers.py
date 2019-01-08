# -*- coding: utf-8 -*-
"""
    weppy.parsers
    -------------

    :copyright: (c) 2014-2019 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

from rapidjson import DM_ISO8601, NM_NATIVE, loads as _json_loads


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


@Parsers.register_for('json')
def json(value):
    return _json_loads(value, datetime_mode=DM_ISO8601, number_mode=NM_NATIVE)
