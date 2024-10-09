# -*- coding: utf-8 -*-
"""
emmett.cache
------------

Provides a caching system.

:copyright: 2014 Giovanni Barillari
:license: BSD-3-Clause
"""

from __future__ import annotations

import os
import pickle
import tempfile
import threading
import time
from typing import Any, List, Optional

from emmett_core.cache import Cache as Cache
from emmett_core.cache.handlers import CacheHandler, RamCache as RamCache, RedisCache as RedisCache

from ._shortcuts import hashlib_sha1
from .ctx import current
from .libs.portalocker import LockedFile


class DiskCache(CacheHandler):
    lock = threading.RLock()
    _fs_transaction_suffix = ".__mt_cache"
    _fs_mode = 0o600

    def __init__(self, cache_dir: str = "cache", threshold: int = 500, default_expire: int = 300):
        super().__init__(default_expire=default_expire)
        self._threshold = threshold
        self._path = os.path.join(current.app.root_path, cache_dir)
        #: create required paths if needed
        if not os.path.exists(self._path):
            os.mkdir(self._path)

    def _get_filename(self, key: str) -> str:
        khash = hashlib_sha1(key).hexdigest()
        return os.path.join(self._path, khash)

    def _del_file(self, filename: str):
        try:
            os.remove(filename)
        except Exception:
            pass

    def _list_dir(self) -> List[str]:
        return [
            os.path.join(self._path, fn)
            for fn in os.listdir(self._path)
            if not fn.endswith(self._fs_transaction_suffix)
        ]

    def _prune(self):
        with self.lock:
            entries = self._list_dir()
            if len(entries) > self._threshold:
                now = time.time()
                try:
                    for i, fpath in enumerate(entries):
                        remove = False
                        f = LockedFile(fpath, "rb")
                        exp = pickle.load(f.file)
                        f.close()
                        remove = exp <= now or i % 3 == 0
                        if remove:
                            self._del_file(fpath)
                except Exception:
                    pass

    def get(self, key: str) -> Any:
        filename = self._get_filename(key)
        try:
            with self.lock:
                now = time.time()
                f = LockedFile(filename, "rb")
                exp = pickle.load(f.file)
                if exp < now:
                    f.close()
                    return None
                val = pickle.load(f.file)
                f.close()
        except Exception:
            return None
        return val

    @CacheHandler._convert_duration_
    def set(self, key: str, value: Any, **kwargs):
        filename = self._get_filename(key)
        filepath = os.path.join(self._path, filename)
        with self.lock:
            self._prune()
            if os.path.exists(filepath):
                self._del_file(filepath)
            try:
                fd, tmp = tempfile.mkstemp(suffix=self._fs_transaction_suffix, dir=self._path)
                with os.fdopen(fd, "wb") as f:
                    pickle.dump(kwargs["expiration"], f, 1)
                    pickle.dump(value, f, pickle.HIGHEST_PROTOCOL)
                os.rename(tmp, filename)
                os.chmod(filename, self._fs_mode)
            except Exception:
                pass

    def clear(self, key: Optional[str] = None):
        with self.lock:
            if key is not None:
                filename = self._get_filename(key)
                try:
                    os.remove(filename)
                    return
                except Exception:
                    return
            for name in self._list_dir():
                self._del_file(name)
