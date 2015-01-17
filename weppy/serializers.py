# -*- coding: utf-8 -*-
"""
    weppy.serializers
    -----------------

    :copyright: (c) 2015 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

import datetime
import decimal
from .language.translator import TElement
from .tags import TAG, tag, xmlescape
from .datastructures import sdict

try:
    import simplejson as json_parser
except ImportError:
    import json as json_parser


def _custom_json(o):
    if hasattr(o, 'custom_json') and callable(o.custom_json):
        return o.custom_json()
    if isinstance(o, (
        datetime.date,
        datetime.datetime,
        datetime.time)
    ):
        return o.isoformat()[:19].replace('T', ' ')
    elif isinstance(o, (int, long)):
        return int(o)
    elif isinstance(o, decimal.Decimal):
        return str(o)
    elif isinstance(o, TElement):
        return str(o)
    elif isinstance(o, TAG):
        return str(o)
    elif hasattr(o, 'as_list') and callable(o.as_list):
        return o.as_list()
    elif hasattr(o, 'as_dict') and callable(o.as_dict):
        return o.as_dict()
    else:
        raise TypeError(repr(o) + " is not JSON serializable")


def json(value, default=_custom_json):
    return json_parser.dumps(value, default=default).replace(
        ur'\u2028', '\\u2028').replace(ur'\2029', '\\u2029')


def _xml_rec(value, key, quote=True):
    if hasattr(value, 'custom_xml') and callable(value.custom_xml):
        return value.custom_xml()
    elif isinstance(value, (dict, sdict)):
        return tag[key](*[tag[k](_xml_rec(v, '', quote))
                          for k, v in value.items()])
    elif isinstance(value, list):
        return tag[key](*[tag[item](_xml_rec(item, '', quote))
                        for item in value])
    elif hasattr(value, 'as_list') and callable(value.as_list):
        return str(_xml_rec(value.as_list(), '', quote))
    elif hasattr(value, 'as_dict') and callable(value.as_dict):
        return str(_xml_rec(value.as_dict(), '', quote))
    else:
        return xmlescape(value, quote)


def xml(value, encoding='UTF-8', key='document', quote=True):
    return ('<?xml version="1.0" encoding="%s"?>' % encoding) + \
        str(_xml_rec(value, key, quote))
