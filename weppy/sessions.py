# -*- coding: utf-8 -*-
"""
    weppy.sessions
    --------------

    Provides session managers for weppy applications.

    :copyright: (c) 2014-2017 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

import os
import time
import tempfile
from ._compat import pickle, to_native
from .security import secure_loads, secure_dumps, uuid
from .pipeline import Pipe
from .globals import current, request, response
from .datastructures import sdict, SessionData


class SessionCookieManager(Pipe):
    def __init__(self, key, secure=False, domain=None):
        self.key = key
        self.secure = secure
        self.domain = domain

    def open(self):
        self.cookie_data_name = 'wpp_session_data_%s' % request.appname
        if self.cookie_data_name in request.cookies:
            cookie_data = request.cookies[self.cookie_data_name].value
            current.session = SessionData(secure_loads(
                cookie_data, self.key), expires=3600)
        if not current.session:
            current.session = SessionData(expires=3600)

    def close(self):
        data = secure_dumps(sdict(current.session), self.key)
        response.cookies[self.cookie_data_name] = data
        response.cookies[self.cookie_data_name]['path'] = "/"
        response.cookies[self.cookie_data_name]['expires'] = \
            current.session._expiration
        if self.secure:
            response.cookies[self.cookie_data_name]['secure'] = True
        if self.domain is not None:
            response.cookies[self.cookie_data_name]['domain'] = self.domain

    def clear(self):
        raise NotImplementedError(
            "%s doesn't support clear of sessions. " +
            "You should change the '%s' parameter to invalidate existing ones."
            % (self.__class__.__name__, 'secure'))


class SessionFSManager(Pipe):
    _fs_transaction_suffix = '.__wp_sess'
    _fs_mode = 0o600

    def __init__(self, expire=3600, secure=False, domain=None,
                 filename_template='weppy_%s.sess'):
        assert not filename_template.endswith(self._fs_transaction_suffix), \
            'filename templates cannot end with %s' % \
            self._fs_transaction_suffix
        self._filename_template = filename_template
        from .expose import Expose
        self._path = os.path.join(Expose.application.root_path, 'sessions')
        #: create required paths if needed
        if not os.path.exists(self._path):
            os.mkdir(self._path)
        self.expire = expire
        self.secure = secure
        self.domain = domain

    def _get_filename(self, sid):
        sid = to_native(sid)
        return os.path.join(self._path, self._filename_template % sid)

    def _load(self, sid):
        try:
            f = open(self._get_filename(sid), 'rb')
        except IOError:
            return None
        now = time.time()
        exp = pickle.load(f)
        val = pickle.load(f)
        f.close()
        if exp < now:
            f.close()
            return None
        return val

    def _store(self, session, expiration):
        fn = self._get_filename(session._sid)
        now = time.time()
        exp = now + expiration
        fd, tmp = tempfile.mkstemp(suffix=self._fs_transaction_suffix,
                                   dir=self._path)
        f = os.fdopen(fd, 'wb')
        try:
            pickle.dump(exp, f, 1)
            #f.write(session._dump)
            pickle.dump(sdict(session), f, pickle.HIGHEST_PROTOCOL)
        finally:
            f.close()
        try:
            os.rename(tmp, fn)
            os.chmod(fn, self._fs_mode)
        except:
            pass

    def _delete(self, session):
        fn = self._get_filename(session._sid)
        try:
            os.unlink(fn)
        except OSError:
            pass

    def open(self):
        self.cookie_data_name = 'wpp_session_data_%s' % request.appname
        if self.cookie_data_name in request.cookies:
            sid = request.cookies[self.cookie_data_name].value
            data = self._load(sid)
            if data is not None:
                current.session = SessionData(data, sid=sid)
        if not current.session:
            sid = uuid()
            current.session = SessionData(sid=sid)

    def close(self):
        if not current.session:
            self._delete(current.session)
            if current.session._modified:
                #: if we got here means we want to destroy session definitely
                if self.cookie_data_name in response.cookies:
                    del response.cookies[self.cookie_data_name]
            return
        #: store and update cookies
        expiration = current.session._expiration or self.expire
        if current.session._modified:
            self._store(current.session, expiration)
        response.cookies[self.cookie_data_name] = current.session._sid
        response.cookies[self.cookie_data_name]['path'] = "/"
        response.cookies[self.cookie_data_name]['expires'] = expiration
        if self.secure:
            response.cookies[self.cookie_data_name]['secure'] = True
        if self.domain is not None:
            response.cookies[self.cookie_data_name]['domain'] = self.domain

    def clear(self):
        for element in os.listdir(self._path):
            os.unlink(os.path.join(self._path, element))


class SessionRedisManager(Pipe):
    def __init__(self, redis, prefix="wppsess:", expire=3600, secure=False,
                 domain=None):
        self.redis = redis
        self.prefix = prefix
        self.expire = expire
        self.secure = secure
        self.domain = domain

    def open(self):
        self.cookie_data_name = 'wpp_session_data_%s' % request.appname
        if self.cookie_data_name in request.cookies:
            sid = request.cookies[self.cookie_data_name].value
            #: load from redis
            data = self.redis.get(self.prefix + sid)
            if data is not None:
                current.session = SessionData(pickle.loads(data), sid=sid)
        if not current.session:
            sid = uuid()
            current.session = SessionData(sid=sid)

    def close(self):
        if not current.session:
            self.redis.delete(self.prefix + current.session._sid)
            if current.session._modified:
                #: if we got here means we want to destroy session definitely
                if self.cookie_data_name in response.cookies:
                    del response.cookies[self.cookie_data_name]
            return
        #: store on redis and update cookies
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

    def clear(self):
        self.redis.delete(self.prefix + "*")
