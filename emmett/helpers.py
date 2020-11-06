# -*- coding: utf-8 -*-
"""
    emmett.helpers
    --------------

    Provides helping methods for applications.

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

import os
import re

from typing import Any, List, Optional, Tuple, Union

from pydal.exceptions import NotAuthorizedException, NotFoundException

from .ctx import current
from .html import HtmlTag, tag
from .http import HTTP, HTTPFile, HTTPIO

_re_dbstream = re.compile(r'(?P<table>.*?)\.(?P<field>.*?)\..*')


def abort(code: int, body: str = ''):
    response = current.response
    response.status = code
    raise HTTP(
        code,
        body=body,
        cookies=response.cookies
    )


def stream_file(path: str):
    full_path = os.path.join(current.app.root_path, path)
    raise HTTPFile(
        full_path,
        headers=current.response.headers,
        cookies=current.response.cookies
    )


def stream_dbfile(db: Any, name: str):
    items = _re_dbstream.match(name)
    if not items:
        abort(404)
    table_name, field_name = items.group('table'), items.group('field')
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
        raise HTTPFile(
            path_or_stream,
            headers=current.response.headers,
            cookies=current.response.cookies
        )
    raise HTTPIO(
        path_or_stream,
        headers=current.response.headers,
        cookies=current.response.cookies
    )


def flash(message: str, category: str = 'message'):
    #: Flashes a message to the next request.
    if current.session._flashes is None:
        current.session._flashes = []
    current.session._flashes.append((category, message))


def get_flashed_messages(
    with_categories: bool = False,
    category_filter: Union[str, List[str]] = []
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


def load_component(
    url: str,
    target: Optional[str] = None,
    content: str = 'loading...'
) -> HtmlTag:
    attr = {}
    if target:
        attr['_id'] = target
    attr['_data-emt_remote'] = url
    return tag.div(content, **attr)
