# -*- coding: utf-8 -*-
"""
    weppy.ctx
    ---------

    Provides the current object. Used by application to deal with
    request, response, session (if loaded with pipeline).

    :copyright: (c) 2014-2018 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

import contextvars
import pendulum

from datetime import datetime

from ._internal import ObjectProxy
# from .globals import Request, Response
from .globals import Response
from .language import T, _instance as _translator_instance
from .utils import cachedprop
from .web.request import Request


class Context(object):
    def __init__(self):
        self.language = None

    @property
    def now(self):
        return pendulum.instance(datetime.utcnow())


class RequestContext(object):
    def __init__(self, scope):
        self.request = Request(scope)
        self.response = Response({})
        self.session = None

    @property
    def now(self):
        return self.request.now

    @cachedprop
    def language(self):
        return self.request.accept_languages.best_match(
            list(_translator_instance._t.all_languages))


class Current(object):
    __slots__ = ('_ctx',)

    def __init__(self):
        # self.ctx = contextvars.ContextVar('ctx')
        object.__setattr__(self, '_ctx', contextvars.ContextVar('ctx'))
        self._ctx.set(Context())

    def _init_(self, scope):
        return self._ctx.set(RequestContext(scope))

    def _close_(self, token):
        self._ctx.reset(token)

    @property
    def ctx(self):
        return self._ctx.get()

    def __getattr__(self, name):
        return getattr(self.ctx, name)

    def __setattr__(self, name, value):
        setattr(self.ctx, name, value)

    @property
    def language(self):
        return self.ctx.language

    @property
    def now(self):
        return self.ctx.now

    @property
    def request(self):
        return self.ctx.request

    @property
    def response(self):
        return self.ctx.response

    @property
    def session(self):
        return self.ctx.session

    @session.setter
    def session(self, val):
        self.ctx.session = val

    @property
    def T(self):
        return T


current = Current()
request = ObjectProxy(current, 'request')
response = ObjectProxy(current, 'response')
session = ObjectProxy(current, 'session')


def now():
    return current.now
