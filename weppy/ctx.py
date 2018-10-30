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
from .globals import Request, Response
from .language import T, _instance as _translator_instance
from .utils import cachedprop


class Context(object):
    __slots__ = ('language',)

    def __init__(self):
        self.language = None

    @property
    def now(self):
        return pendulum.instance(datetime.utcnow())


class RequestContext(object):
    __slots__ = ('request', 'response', 'session')

    def __init__(self, environ):
        self.request = Request(environ)
        self.response = Response(environ)
        self.session = None

    @property
    def now(self):
        return self.request.now

    @cachedprop
    def language(self):
        return self.request.accept_languages.best_match(
            list(_translator_instance._t.all_languages))


class Current(object):
    __slots__ = ('ctx',)

    def __init__(self):
        self.ctx = contextvars.ContextVar('ctx')
        self.ctx.set(Context())

    def _init_(self, environ):
        return self.ctx.set(RequestContext(environ))

    def _close_(self, token):
        self.ctx.reset(token)

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

    @session.set
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
