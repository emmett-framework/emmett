# -*- coding: utf-8 -*-
"""
emmett.helpers
--------------

Provides helping methods for applications.

:copyright: 2014 Giovanni Barillari
:license: BSD-3-Clause
"""

from typing import Any, List, Optional, Tuple, Union

from emmett_core._internal import deprecated
from emmett_core.http.helpers import abort as _abort

from .ctx import current
from .html import HtmlTag, tag


def abort(code: int, body: str = ""):
    _abort(current, code, body)


@deprecated("stream_file", "Response.wrap_file")
def stream_file(path: str):
    raise current.response.wrap_file(path)


@deprecated("stream_dbfile", "Response.wrap_dbfile")
def stream_dbfile(db: Any, name: str):
    raise current.response.wrap_dbfile(db, name)


def flash(message: str, category: str = "message"):
    #: Flashes a message to the next request.
    if current.session._flashes is None:
        current.session._flashes = []
    current.session._flashes.append((category, message))


def get_flashed_messages(
    with_categories: bool = False, category_filter: Union[str, List[str]] = []
) -> Union[List[str], Tuple[str, str]]:
    #: Pulls flashed messages from the session and returns them.
    #  By default just the messages are returned, but when `with_categories`
    #  is set to `True`, the return value will be a list of tuples in the
    #  form `(category, message)` instead.
    if not isinstance(category_filter, list):
        category_filter = [category_filter]
    try:
        flashes = list(current.session._flashes or [])
        if category_filter:
            flashes = list(filter(lambda f: f[0] in category_filter, flashes))
        for el in flashes:
            current.session._flashes.remove(el)
        if not with_categories:
            return [x[1] for x in flashes]
    except Exception:
        flashes = []
    return flashes


def load_component(url: str, target: Optional[str] = None, content: str = "loading...") -> HtmlTag:
    attr = {}
    if target:
        attr["_id"] = target
    attr["_data-emt_remote"] = url
    return tag.div(content, **attr)
