# -*- coding: utf-8 -*-
"""
    emmett.locals
    -------------

    Provides shortcuts to `current` object.

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

from typing import Optional, cast

from pendulum import DateTime

from ._internal import ContextVarProxy as _VProxy, ObjectProxy as _OProxy
from .ctx import current
from .datastructures import sdict
from .language.translator import Translator
from .wrappers.request import Request
from .wrappers.response import Response
from .wrappers.websocket import Websocket

request = cast(Request, _VProxy[Request](current._ctx, 'request'))
response = cast(Response, _VProxy[Response](current._ctx, 'response'))
session = cast(Optional[sdict], _VProxy[Optional[sdict]](current._ctx, 'session'))
websocket = cast(Websocket, _VProxy[Websocket](current._ctx, 'websocket'))
T = cast(Translator, _OProxy[Translator](current, 'T'))


def now() -> DateTime:
    return current.now
