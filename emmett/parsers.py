# -*- coding: utf-8 -*-
"""
    emmett.parsers
    --------------

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

from functools import partial
from typing import Any, Callable, Dict

try:
    import orjson
    _json_impl = orjson.loads
    _json_opts = {}
except ImportError:
    import rapidjson
    _json_impl = rapidjson.loads
    _json_opts = {
        "datetime_mode": rapidjson.DM_ISO8601 | rapidjson.DM_NAIVE_IS_UTC,
        "number_mode": rapidjson.NM_NATIVE
    }


class Parsers(object):
    _registry_: Dict[str, Callable[[str], Dict[str, Any]]] = {}

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
    _json_impl,
    **_json_opts
)

Parsers.register_for('json')(json)
