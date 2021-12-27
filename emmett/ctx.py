# -*- coding: utf-8 -*-
"""
    emmett.ctx
    ----------

    Provides the current object.
    Used by application to deal with request related objects.

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

import contextvars

from datetime import datetime
from typing import Any

import pendulum

from .utils import cachedprop

_ctxv = contextvars.ContextVar("_emt_ctxv")


class Context:
    __slots__ = ["app", "__dict__"]

    def __init__(self):
        self.language = None

    @property
    def now(self):
        return pendulum.instance(datetime.utcnow())


class RequestContext(Context):
    __slots__ = ["request", "response", "session"]

    def __init__(
        self,
        app,
        request,
        response
    ):
        self.app = app
        self.request = request
        self.response = response
        self.session = None

    @property
    def now(self):
        return self.request.now

    @cachedprop
    def language(self):
        return self.request.accept_language.best_match(
            list(self.app.translator._langmap)
        )


class WSContext(Context):
    __slots__ = ["websocket", "session"]

    def __init__(self, app, websocket):
        self.app = app
        self.websocket = websocket
        self.session = None

    @cachedprop
    def language(self):
        return self.websocket.accept_language.best_match(
            list(self.app.translator._langmap)
        )


class Current:
    __slots__ = []

    ctx = property(_ctxv.get)

    def __init__(self):
        _ctxv.set(Context())

    def _init_(self, ctx):
        return _ctxv.set(ctx)

    def _close_(self, token):
        _ctxv.reset(token)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.ctx, name)

    def __setattr__(self, name: str, value: Any):
        setattr(self.ctx, name, value)

    def __delattr__(self, name: str):
        delattr(self.ctx, name)

    def __getitem__(self, name: str) -> Any:
        try:
            return getattr(self.ctx, name)
        except AttributeError as e:
            raise KeyError from e

    def __setitem__(self, name: str, value: Any):
        setattr(self.ctx, name, value)

    def __delitem__(self, name: str):
        delattr(self.ctx, name)

    def __contains__(self, name: str) -> bool:
        return hasattr(self.ctx, name)

    def get(self, name: str, default: Any = None) -> Any:
        return getattr(self.ctx, name, default)

    @property
    def T(self):
        return self.ctx.app.translator


current = Current()
