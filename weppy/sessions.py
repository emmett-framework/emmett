# -*- coding: utf-8 -*-
"""
    weppy.sessions
    --------------

    Provides session managers for weppy applications.

    :copyright: (c) 2014-2018 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

import os
import time
import tempfile

from ._compat import pickle, to_native
from ._internal import warn_of_deprecation
from .datastructures import sdict, SessionData
from .expose import Expose
from .globals import current, request, response
from .pipeline import Pipe
from .security import secure_loads, secure_dumps, uuid


class SessionPipe(Pipe):
    def __init__(
        self, expire=3600, secure=False, domain=None, cookie_name=None
    ):
        self.expire = expire
        self.secure = secure
        self.domain = domain
        self.cookie_name = (
            cookie_name or 'wpp_session_data_%s' % Expose.application.name)

    def _load_session(self):
        pass

    def _new_session(self):
        pass

    def _pack_session(self, expiration):
        response.cookies[self.cookie_name] = self._session_cookie_data()
        response.cookies[self.cookie_name]['path'] = "/"
        response.cookies[self.cookie_name]['expires'] = expiration
        if self.secure:
            response.cookies[self.cookie_name]['secure'] = True
        if self.domain is not None:
            response.cookies[self.cookie_name]['domain'] = self.domain

    def _session_cookie_data(self):
        pass

    def open(self):
        if self.cookie_name in request.cookies:
            current.session = self._load_session()
        if not current.session:
            current.session = self._new_session()

    def close(self):
        expiration = current.session._expiration or self.expire
        self._pack_session(expiration)

    def clear(self):
        pass


class CookieSessionPipe(SessionPipe):
    def __init__(
        self, key, expire=3600, secure=False, domain=None, cookie_name=None
    ):
        super(CookieSessionPipe, self).__init__(
            expire, secure, domain, cookie_name)
        self.key = key

    def _load_session(self):
        cookie_data = request.cookies[self.cookie_name].value
        return SessionData(
            secure_loads(cookie_data, self.key), expires=self.expire)

    def _new_session(self):
        return SessionData(expires=self.expire)

    def _session_cookie_data(self):
        return secure_dumps(sdict(current.session), self.key)

    def clear(self):
        raise NotImplementedError(
            "%s doesn't support sessions clearing. " +
            "You should change the '%s' parameter to invalidate existing ones."
            % (self.__class__.__name__, 'key'))


class BackendStoredSessionPipe(SessionPipe):
    def _new_session(self):
        return SessionData(sid=uuid())

    def _session_cookie_data(self):
        return current.session._sid

    def _load_session(self):
        sid = request.cookies[self.cookie_name].value
        data = self._load(sid)
        if data is not None:
            return SessionData(data, sid=sid)
        return None

    def _delete_session(self):
        pass

    def _save_session(self, expiration):
        pass

    def _load(self, sid):
        return None

    def close(self):
        if not current.session:
            self._delete_session()
            if current.session._modified:
                #: if we got here means we want to destroy session definitely
                if self.cookie_name in response.cookies:
                    del response.cookies[self.cookie_name]
            return
        expiration = current.session._expiration or self.expire
        self._save_session(expiration)
        self._pack_session(expiration)


class FileSessionPipe(BackendStoredSessionPipe):
    _fs_transaction_suffix = '.__wp_sess'
    _fs_mode = 0o600

    def __init__(
        self, expire=3600, secure=False, domain=None, cookie_name=None,
        filename_template='weppy_%s.sess'
    ):
        super(FileSessionPipe, self).__init__(
            expire, secure, domain, cookie_name)
        assert not filename_template.endswith(self._fs_transaction_suffix), \
            'filename templates cannot end with %s' % \
            self._fs_transaction_suffix
        self._filename_template = filename_template
        self._path = os.path.join(Expose.application.root_path, 'sessions')
        #: create required paths if needed
        if not os.path.exists(self._path):
            os.mkdir(self._path)

    def _delete_session(self):
        fn = self._get_filename(current.session._sid)
        try:
            os.unlink(fn)
        except OSError:
            pass

    def _save_session(self, expiration):
        if current.session._modified:
            self._store(current.session, expiration)

    def _get_filename(self, sid):
        sid = to_native(sid)
        return os.path.join(self._path, self._filename_template % sid)

    def _load(self, sid):
        try:
            with open(self._get_filename(sid), 'rb') as f:
                exp = pickle.load(f)
                val = pickle.load(f)
        except IOError:
            return None
        if exp < time.time():
            return None
        return val

    def _store(self, session, expiration):
        fn = self._get_filename(session._sid)
        now = time.time()
        exp = now + expiration
        fd, tmp = tempfile.mkstemp(
            suffix=self._fs_transaction_suffix, dir=self._path)
        f = os.fdopen(fd, 'wb')
        try:
            pickle.dump(exp, f, 1)
            pickle.dump(sdict(session), f, pickle.HIGHEST_PROTOCOL)
        finally:
            f.close()
        try:
            os.rename(tmp, fn)
            os.chmod(fn, self._fs_mode)
        except Exception:
            pass

    def clear(self):
        for element in os.listdir(self._path):
            try:
                os.unlink(os.path.join(self._path, element))
            except Exception:
                pass


class RedisSessionPipe(BackendStoredSessionPipe):
    def __init__(
        self, redis, prefix="wppsess:", expire=3600, secure=False, domain=None,
        cookie_name=None
    ):
        super(RedisSessionPipe, self).__init__(
            expire, secure, domain, cookie_name)
        self.redis = redis
        self.prefix = prefix

    def _delete_session(self):
        self.redis.delete(self.prefix + current.session._sid)

    def _save_session(self, expiration):
        if current.session._modified:
            self.redis.setex(
                self.prefix + current.session._sid, current.session._dump,
                expiration)
        else:
            self.redis.expire(self.prefix + current.session._sid, expiration)

    def _load(self, sid):
        data = self.redis.get(self.prefix + sid)
        return pickle.loads(data) if data else data

    def clear(self):
        self.redis.delete(self.prefix + "*")


class SessionManager(object):
    _pipe = None

    @classmethod
    def _build_pipe(cls, handler_cls, *args, **kwargs):
        cls._pipe = handler_cls(*args, **kwargs)
        return cls._pipe

    @classmethod
    def cookies(
        cls, key, expire=3600, secure=False, domain=None, cookie_name=None
    ):
        return cls._build_pipe(
            CookieSessionPipe, key, expire=expire, secure=secure,
            domain=domain, cookie_name=cookie_name)

    @classmethod
    def files(
        cls, expire=3600, secure=False, domain=None, cookie_name=None,
        filename_template='weppy_%s.sess'
    ):
        return cls._build_pipe(
            FileSessionPipe, expire=expire, secure=secure, domain=domain,
            cookie_name=cookie_name, filename_template=filename_template)

    @classmethod
    def redis(
        cls, redis, prefix="wppsess:", expire=3600, secure=False, domain=None,
        cookie_name=None
    ):
        return cls._build_pipe(
            RedisSessionPipe, redis, prefix=prefix, expire=expire,
            secure=secure, domain=domain, cookie_name=cookie_name)

    @classmethod
    def clear(cls):
        cls._pipe.clear()
