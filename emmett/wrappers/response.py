# -*- coding: utf-8 -*-
"""
emmett.wrappers.response
------------------------

Provides response wrappers.

:copyright: 2014 Giovanni Barillari
:license: BSD-3-Clause
"""

import os
import re
from typing import Any

from emmett_core.http.response import HTTPFileResponse, HTTPResponse
from emmett_core.http.wrappers.response import Response as _Response
from emmett_core.utils import cachedprop
from pydal.exceptions import NotAuthorizedException, NotFoundException

from ..ctx import current
from ..datastructures import sdict
from ..helpers import abort, get_flashed_messages
from ..html import htmlescape


_re_dbstream = re.compile(r"(?P<table>.*?)\.(?P<field>.*?)\..*")


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
        return [(key, htmlescape(val)) for key, val in self.meta.items()]

    def _meta_tmpl_prop(self):
        return [(key, htmlescape(val)) for key, val in self.meta_prop.items()]

    def wrap_file(self, path) -> HTTPFileResponse:
        path = os.path.join(current.app.root_path, path)
        return super().wrap_file(path)

    def wrap_dbfile(self, db, name: str) -> HTTPResponse:
        items = _re_dbstream.match(name)
        if not items:
            abort(404)
        table_name, field_name = items.group("table"), items.group("field")
        try:
            field = db[table_name][field_name]
        except AttributeError:
            abort(404)
        try:
            filename, path_or_stream = field.retrieve(name, nameonly=True)
        except NotAuthorizedException:
            abort(403)
        except NotFoundException:
            abort(404)
        except IOError:
            abort(404)
        if isinstance(path_or_stream, str):
            return self.wrap_file(path_or_stream)
        return self.wrap_io(path_or_stream)
