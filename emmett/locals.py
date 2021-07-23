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
from .ctx import _ctxv, current
from .datastructures import sdict
from .language.translator import Translator
from .wrappers.request import Request
from .wrappers.response import Response
from .wrappers.websocket import Websocket

request = cast(Request, _VProxy[Request](_ctxv, 'request'))
response = cast(Response, _VProxy[Response](_ctxv, 'response'))
session = cast(Optional[sdict], _VProxy[Optional[sdict]](_ctxv, 'session'))
websocket = cast(Websocket, _VProxy[Websocket](_ctxv, 'websocket'))
T = cast(Translator, _OProxy[Translator](current, 'T'))


def now() -> DateTime:
    return current.now
