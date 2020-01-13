# -*- coding: utf-8 -*-
"""
    emmett.ctx
    ----------

    Provides the current object. Used by application to deal with
    request, response, session (if loaded with pipeline).

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

import contextvars
import pendulum

from datetime import datetime

from ._internal import ContextVarProxy


class Context:
    def __init__(self):
        self.language = None

    @property
    def now(self):
        return pendulum.instance(datetime.utcnow())


class Current:
    __slots__ = ['_ctx']

    def __init__(self):
        object.__setattr__(self, '_ctx', contextvars.ContextVar('ctx'))
        self._ctx.set(Context())

    def _init_(self, ctx_cls, app, scope, *args, **kwargs):
        return self._ctx.set(ctx_cls(app, scope, *args, **kwargs))

    def _close_(self, token):
        self._ctx.reset(token)

    @property
    def ctx(self):
        return self._ctx.get()

    def __getattr__(self, name):
        return getattr(self.ctx, name)

    def __setattr__(self, name, value):
        setattr(self.ctx, name, value)

    def __delattr__(self, name):
        delattr(self.ctx, name)

    @property
    def T(self):
        return self.ctx.app.translator


current = Current()
request = ContextVarProxy(current._ctx, 'request')
response = ContextVarProxy(current._ctx, 'response')
session = ContextVarProxy(current._ctx, 'session')
websocket = ContextVarProxy(current._ctx, 'websocket')


def now():
    return current.now
