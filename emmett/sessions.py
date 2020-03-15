# -*- coding: utf-8 -*-
"""
    emmett.sessions
    ---------------

    Provides session managers for applications.

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

from __future__ import annotations

import os
import pickle
import tempfile
import time

from typing import Any, Optional, Type

from .ctx import current, request, response, websocket
from .datastructures import sdict, SessionData
from .pipeline import Pipe
from .security import secure_loads, secure_dumps, uuid
from .wrappers import ScopeWrapper


class SessionPipe(Pipe):
    def __init__(
        self, expire=3600, secure=False, domain=None, cookie_name=None
    ):
        self.expire = expire
        self.secure = secure
        self.domain = domain
        self.cookie_name = (
            cookie_name or f'emt_session_data_{current.app.name}'
        )

    def _load_session(self, wrapper: ScopeWrapper):
        raise NotImplementedError

    def _new_session(self) -> SessionData:
        raise NotImplementedError

    def _pack_session(self, expiration: int):
        response.cookies[self.cookie_name] = self._session_cookie_data()
        cookie_data = response.cookies[self.cookie_name]
        cookie_data['path'] = "/"
        cookie_data['expires'] = expiration
        if self.secure:
            cookie_data['secure'] = True
        if self.domain is not None:
            cookie_data['domain'] = self.domain

    def _session_cookie_data(self) -> str:
        raise NotImplementedError

    async def open_request(self):
        if self.cookie_name in request.cookies:
            current.session = self._load_session(request)
        if not current.session:
            current.session = self._new_session()

    async def open_ws(self):
        if self.cookie_name in websocket.cookies:
            current.session = self._load_session(websocket)
        if not current.session:
            current.session = self._new_session()

    async def close_request(self):
        expiration = current.session._expiration or self.expire
        self._pack_session(expiration)

    def clear(self):
        pass


class CookieSessionPipe(SessionPipe):
    def __init__(
        self, key, expire=3600, secure=False, domain=None, cookie_name=None
    ):
        super().__init__(expire, secure, domain, cookie_name)
        self.key = key

    def _load_session(self, wrapper: ScopeWrapper) -> SessionData:
        cookie_data = wrapper.cookies[self.cookie_name].value
        return SessionData(
            secure_loads(cookie_data, self.key),
            expires=self.expire
        )

    def _new_session(self) -> SessionData:
        return SessionData(expires=self.expire)

    def _session_cookie_data(self) -> str:
        return secure_dumps(sdict(current.session), self.key)

    def clear(self):
        raise NotImplementedError(
            f"{self.__class__.__name__} doesn't support sessions clearing. "
            f"Change the 'key' parameter to invalidate existing ones."
        )


class BackendStoredSessionPipe(SessionPipe):
    def _new_session(self):
        return SessionData(sid=uuid())

    def _session_cookie_data(self) -> str:
        return current.session._sid

    def _load_session(self, wrapper: ScopeWrapper) -> Optional[SessionData]:
        sid = wrapper.cookies[self.cookie_name].value
        data = self._load(sid)
        if data is not None:
            return SessionData(data, sid=sid)
        return None

    def _delete_session(self):
        pass

    def _save_session(self, expiration: int):
        pass

    def _load(self, sid: str):
        return None

    async def close_request(self):
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
    _fs_transaction_suffix = '.__emt_sess'
    _fs_mode = 0o600

    def __init__(
        self, expire=3600, secure=False, domain=None, cookie_name=None,
        filename_template='emt_%s.sess'
    ):
        super().__init__(expire, secure, domain, cookie_name)
        assert not filename_template.endswith(self._fs_transaction_suffix), \
            'filename templates cannot end with %s' % \
            self._fs_transaction_suffix
        self._filename_template = filename_template
        self._path = os.path.join(current.app.root_path, 'sessions')
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
        return os.path.join(self._path, self._filename_template % str(sid))

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
        self, redis, prefix="emtsess:", expire=3600, secure=False, domain=None,
        cookie_name=None
    ):
        super().__init__(expire, secure, domain, cookie_name)
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


class SessionManager:
    _pipe: Optional[SessionPipe] = None

    @classmethod
    def _build_pipe(
        cls,
        handler_cls: Type[SessionPipe],
        *args,
        **kwargs
    ) -> SessionPipe:
        cls._pipe = handler_cls(*args, **kwargs)
        return cls._pipe

    @classmethod
    def cookies(
        cls,
        key: str,
        expire: int = 3600,
        secure: bool = False,
        domain: Optional[str] = None,
        cookie_name: Optional[str] = None
    ) -> CookieSessionPipe:
        return cls._build_pipe(
            CookieSessionPipe,
            key,
            expire=expire,
            secure=secure,
            domain=domain,
            cookie_name=cookie_name
        )

    @classmethod
    def files(
        cls,
        expire: int = 3600,
        secure: bool = False,
        domain: Optional[str] = None,
        cookie_name: Optional[str] = None,
        filename_template: str = 'emt_%s.sess'
    ) -> FileSessionPipe:
        return cls._build_pipe(
            FileSessionPipe,
            expire=expire,
            secure=secure,
            domain=domain,
            cookie_name=cookie_name,
            filename_template=filename_template
        )

    @classmethod
    def redis(
        cls,
        redis: Any,
        prefix: str = "emtsess:",
        expire: int = 3600,
        secure: bool = False,
        domain: Optional[str] = None,
        cookie_name: Optional[str] = None
    ) -> RedisSessionPipe:
        return cls._build_pipe(
            RedisSessionPipe,
            redis,
            prefix=prefix,
            expire=expire,
            secure=secure,
            domain=domain,
            cookie_name=cookie_name
        )

    @classmethod
    def clear(cls):
        cls._pipe.clear()
