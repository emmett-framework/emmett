# -*- coding: utf-8 -*-
"""
    emmett.wrappers.response
    ------------------------

    Provides response wrappers.

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

from typing import Any

from emmett_core.http.wrappers.response import Response as _Response
from emmett_core.utils import cachedprop

from ..datastructures import sdict
from ..helpers import get_flashed_messages
from ..html import htmlescape


class Response(_Response):
    __slots__ = ()

    @cachedprop
    def meta(self) -> sdict[str, Any]:
        return sdict()

    @cachedprop
    def meta_prop(self) -> sdict[str, Any]:
        return sdict()

    def alerts(self, **kwargs):
        return get_flashed_messages(**kwargs)

    def _meta_tmpl(self):
        return [
            (key, htmlescape(val)) for key, val in self.meta.items()
        ]

    def _meta_tmpl_prop(self):
        return [
            (key, htmlescape(val)) for key, val in self.meta_prop.items()
        ]
