# -*- coding: utf-8 -*-
"""
emmett.ctx
----------

Provides the current object.
Used by application to deal with request related objects.

:copyright: 2014 Giovanni Barillari
:license: BSD-3-Clause
"""

from datetime import datetime

import pendulum
from emmett_core.ctx import (
    Context as _Context,
    Current as _Current,
    RequestContext as _RequestContext,
    WSContext as _WsContext,
    _ctxv,
)
from emmett_core.utils import cachedprop


class Context(_Context):
    __slots__ = []

    @property
    def now(self):
        return pendulum.instance(datetime.utcnow())


class RequestContext(_RequestContext):
    __slots__ = []

    @cachedprop
    def language(self):
        return self.request.accept_language.best_match(list(self.app.translator._langmap))


class WSContext(_WsContext):
    __slots__ = []

    @property
    def now(self):
        return pendulum.instance(datetime.utcnow())

    @cachedprop
    def language(self):
        return self.websocket.accept_language.best_match(list(self.app.translator._langmap))


class Current(_Current):
    __slots__ = []

    def __init__(self):
        _ctxv.set(Context())

    @property
    def T(self):
        return self.ctx.app.translator


current = Current()
