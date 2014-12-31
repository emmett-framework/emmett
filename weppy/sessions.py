# -*- coding: utf-8 -*-
"""
    weppy.sessions
    --------------

    Provides session handlers for weppy applications.

    :copyright: (c) 2014 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

from ._compat import pickle
from .security import secure_loads, secure_dumps, uuid
from .handlers import Handler
from .globals import current, request, response
from .datastructures import sdict, SessionData


class SessionCookieManager(Handler):
    def __init__(self, key, secure=False, domain=None):
        self.key = key
        self.secure = secure
        self.domain = domain

    def on_start(self):
        self.cookie_data_name = 'wpp_session_data_%s' % request.application
        if self.cookie_data_name in request.cookies:
            cookie_data = request.cookies[self.cookie_data_name].value
            current.session = SessionData(secure_loads(
                cookie_data, self.key), expires=3600)
        if not current.session:
            current.session = SessionData(expires=3600)
        #(current.response.flash, current.session.flash) = (current.session.flash, None)

    def on_success(self):
        data = secure_dumps(sdict(current.session), self.key)
        response.cookies[self.cookie_data_name] = data
        response.cookies[self.cookie_data_name]['path'] = "/"
        response.cookies[self.cookie_data_name]['expires'] = \
            current.session._expiration
        if self.secure:
            response.cookies[self.cookie_data_name]['secure'] = True
        if self.domain is not None:
            response.cookies[self.cookie_data_name]['domain'] = self.domain

    def on_failure(self):
        self.on_success()


class SessionRedisManager(Handler):
    def __init__(self, redis, prefix="wppsess:", expire=3600, secure=False,
                 domain=None):
        self.redis = redis
        self.prefix = prefix
        self.expire = expire
        self.secure = secure
        self.domain = domain

    def on_start(self):
        self.cookie_data_name = 'wpp_session_data_%s' % request.application
        if self.cookie_data_name in request.cookies:
            sid = request.cookies[self.cookie_data_name].value
            ## load from redis
            data = self.redis.get(self.prefix+sid)
            if data is not None:
                current.session = SessionData(pickle.loads(data), sid=sid)
        if not current.session:
            sid = uuid()
            current.session = SessionData(sid=sid)

    def on_success(self):
        if not current.session:
            self.redis.delete(self.prefix+current.session._sid)
            if current.session._modified:
                ## if we got here means we want to destroy session definitely
                if self.cookie_data_name in response.cookies:
                    del response.cookies[self.cookie_data_name]
            return
        ## store on redis
        expiration = current.session._expiration or self.expire
        if current.session._modified:
            self.redis.setex(self.prefix + current.session._sid,
                             current.session._dump, expiration)
        else:
            self.redis.expire(self.prefix + current.session._sid, expiration)
        response.cookies[self.cookie_data_name] = current.session._sid
        response.cookies[self.cookie_data_name]['path'] = "/"
        response.cookies[self.cookie_data_name]['expires'] = expiration
        if self.secure:
            response.cookies[self.cookie_data_name]['secure'] = True
        if self.domain is not None:
            response.cookies[self.cookie_data_name]['domain'] = self.domain

    def on_failure(self):
        self.on_success()
