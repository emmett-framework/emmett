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
        scope,
        receive,
        send,
        wrapper_request,
        wrapper_response
    ):
        self.app = app
        self.request = wrapper_request(
            scope,
            receive,
            send,
            app.config.request_max_content_length,
            app.config.request_body_timeout
        )
        self.response = wrapper_response()
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

    def __init__(self, app, scope, receive, send, wrapper_websocket):
        self.app = app
        self.websocket = wrapper_websocket(
            scope,
            receive,
            send
        )
        self.session = None

    @cachedprop
    def language(self):
        return self.websocket.accept_language.best_match(
            list(self.app.translator._langmap)
        )


class Current:
    __slots__ = ['_ctx']

    def __init__(self):
        object.__setattr__(self, '_ctx', contextvars.ContextVar('ctx'))
        self._ctx.set(Context())

    def _init_(self, ctx):
        return self._ctx.set(ctx)

    def _close_(self, token):
        self._ctx.reset(token)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._ctx.get(), name)

    def __setattr__(self, name: str, value: Any):
        setattr(self._ctx.get(), name, value)

    def __delattr__(self, name: str):
        delattr(self._ctx.get(), name)

    def __getitem__(self, name: str) -> Any:
        try:
            return getattr(self._ctx.get(), name)
        except AttributeError as e:
            raise KeyError from e

    def __setitem__(self, name: str, value: Any):
        setattr(self._ctx.get(), name, value)

    def __delitem__(self, name: str):
        delattr(self._ctx.get(), name)

    def __contains__(self, name: str) -> bool:
        return hasattr(self._ctx.get(), name)

    def get(self, name: str, default: Any = None) -> Any:
        return getattr(self._ctx.get(), name, default)

    @property
    def T(self):
        return self._ctx.get().app.translator

    @property
    def ctx(self):
        return self._ctx.get()


current = Current()
