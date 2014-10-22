# -*- coding: utf-8 -*-
"""
    weppy.sessions
    --------------

    Provides session handlers and utitilites for weppy applications.

    :copyright: (c) 2014 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

import cPickle
import hashlib
from .security import secure_loads, secure_dumps, uuid
from .handlers import Handler
from .globals import current, request, response
from .storage import Storage


class SessionStorage(Storage):
    __slots__ = ('__sid', '__hash', '__expires', '__dump')

    def __init__(self, initial=None, sid=None, expires=None):
        Storage.__init__(self, initial or ())
        object.__setattr__(self, '_SessionStorage__dump',
                           cPickle.dumps(Storage(self)))
        h = hashlib.md5(self._dump).hexdigest()
        object.__setattr__(self, '_SessionStorage__sid', sid)
        object.__setattr__(self, '_SessionStorage__hash', h)
        object.__setattr__(self, '_SessionStorage__expires', expires)

    @property
    def _sid(self):
        return self.__sid

    @property
    def _modified(self):
        dump = cPickle.dumps(Storage(self))
        h = hashlib.md5(dump).hexdigest()
        if h != self.__hash:
            object.__setattr__(self, '_SessionStorage__dump', dump)
            return True
        return False

    @property
    def _expiration(self):
        return self.__expires

    @property
    def _dump(self):
        ## note: self.__dump is updated only on _modified call
        return self.__dump

    def _expires_after(self, value):
        object.__setattr__(self, '_SessionStorage__expires', value)


class SessionCookieManager(Handler):
    def __init__(self, key, secure=False, domain=None):
        self.key = key
        self.secure = secure
        self.domain = domain

    def on_start(self):
        self.cookie_data_name = 'wpp_session_data_%s' % request.application
        if self.cookie_data_name in request.cookies:
            cookie_data = request.cookies[self.cookie_data_name].value
            current.session = SessionStorage(secure_loads(
                cookie_data, self.key), expires=3600)
        if not current.session:
            current.session = SessionStorage(expires=3600)
        #(current.response.flash, current.session.flash) = (current.session.flash, None)

    def on_success(self):
        data = secure_dumps(Storage(current.session), self.key)
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
                current.session = SessionStorage(cPickle.loads(data), sid=sid)
        if not current.session:
            sid = uuid()
            current.session = SessionStorage(sid=sid)

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
