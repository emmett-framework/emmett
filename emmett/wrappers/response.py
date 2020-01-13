# -*- coding: utf-8 -*-
"""
    emmett.wrappers.response
    ------------------------

    Provides response wrappers.

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

from http.cookies import SimpleCookie

from ..datastructures import sdict
from ..helpers import get_flashed_messages
from ..html import htmlescape
from . import Wrapper


class Response(Wrapper):
    def __init__(self):
        self.status = 200
        self.cookies = SimpleCookie()
        self.headers = {'Content-Type': 'text/html; charset=utf-8'}
        self.meta = sdict()
        self.meta_prop = sdict()

    def alerts(self, **kwargs):
        return get_flashed_messages(**kwargs)

    def _meta_tmpl(self):
        return [
            (key, htmlescape(val)) for key, val in self.meta.items()]

    def _meta_tmpl_prop(self):
        return [
            (key, htmlescape(val)) for key, val in self.meta_prop.items()]
