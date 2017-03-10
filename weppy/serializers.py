# -*- coding: utf-8 -*-
"""
    weppy.serializers
    -----------------

    :copyright: (c) 2014-2017 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

import datetime
import decimal
import json as _json
from ._compat import PY2, integer_types, itervalues
from .html import tag, htmlescape


_json_safe_table = {
    'u2028': [r'\u2028', '\\u2028'],
    'u2029': [r'\u2029', '\\u2029']
}

if PY2:
    _json_safe_table['u2028'][0] = \
        _json_safe_table['u2028'][0].decode('raw_unicode_escape')
    _json_safe_table['u2029'][0] = \
        _json_safe_table['u2029'][0].decode('raw_unicode_escape')


class Serializers(object):
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


class JSONEncoder(_json.JSONEncoder):
    def default(self, o):
        if hasattr(o, '__json__'):
            return o.__json__()
        if isinstance(o, datetime.datetime):
            return o.strftime('%Y-%m-%dT%H:%M:%S.%f%_z')
        if isinstance(o, (datetime.date, datetime.time)):
            return o.isoformat()
        if isinstance(o, integer_types):
            return int(o)
        if isinstance(o, decimal.Decimal):
            return str(o)
        return _json.JSONEncoder.default(self, o)


def _pydal_json_encode(o):
    if hasattr(o, '__json__'):
        return o.__json__()
    raise TypeError(repr(o) + " is not JSON serializable")


@Serializers.register_for('json')
def json(value):
    return _json.dumps(value, cls=JSONEncoder)


def json_safe(value):
    rv = json(value)
    for val, rep in itervalues(_json_safe_table):
        rv.replace(val, rep)
    return rv


def xml_encode(value, key=None, quote=True):
    if hasattr(value, '__xml__'):
        return value.__xml__(key, quote)
    if isinstance(value, dict):
        return tag[key](
            *[
                tag[k](xml_encode(v, None, quote))
                for k, v in value.items()
            ])
    if isinstance(value, list):
        return tag[key](
            *[
                tag[item](xml_encode(item, None, quote))
                for item in value
            ])
    return htmlescape(value, quote)


@Serializers.register_for('xml')
def xml(value, encoding='UTF-8', key='document', quote=True):
    rv = ('<?xml version="1.0" encoding="%s"?>' % encoding) + \
        str(xml_encode(value, key, quote))
    return rv
