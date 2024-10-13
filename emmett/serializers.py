# -*- coding: utf-8 -*-
"""
emmett.serializers
------------------

:copyright: 2014 Giovanni Barillari
:license: BSD-3-Clause
"""

from emmett_core.serializers import Serializers as Serializers

from .html import htmlescape, tag


def xml_encode(value, key=None, quote=True):
    if hasattr(value, "__xml__"):
        return value.__xml__(key, quote)
    if isinstance(value, dict):
        return tag[key](*[tag[k](xml_encode(v, None, quote)) for k, v in value.items()])
    if isinstance(value, list):
        return tag[key](*[tag[item](xml_encode(item, None, quote)) for item in value])
    return htmlescape(value)


@Serializers.register_for("xml")
def xml(value, encoding="UTF-8", key="document", quote=True):
    rv = ('<?xml version="1.0" encoding="%s"?>' % encoding) + str(xml_encode(value, key, quote))
    return rv
