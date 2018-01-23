# -*- coding: utf-8 -*-
"""
    weppy.templating.cache
    ----------------------

    Provides cache for templating system.

    :copyright: (c) 2014-2018 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

import os
import hashlib
from .._compat import to_bytes
from ..utils import cachedprop


def make_hash(value):
    return hashlib.sha1(to_bytes(value)).hexdigest()[:8]


class TemplaterCache(object):
    def __init__(self, app, templater):
        self.app = app
        self.templater = templater
        self.tpath = app.template_path
        self.load = LoaderCache(self)
        self.prerender = PrerenderCache(self)
        self.parse = ParserCache(self)

    @cachedprop
    def changes(self):
        return self.app.debug or self.app.config.templates_auto_reload


class InnerCache(object):
    def __init__(self, cache_interface):
        self.cache = cache_interface
        self.data = {}


class ReloadableMixin(object):
    @cachedprop
    def get(self):
        if self.cache.changes:
            return self.reloader_get
        return self.cached_get


class LoaderCache(InnerCache, ReloadableMixin):
    def __init__(self, cache_interface):
        super(LoaderCache, self).__init__(cache_interface)
        self.mtimes = {}

    def reloader_get(self, file_path):
        try:
            mtime = os.stat(file_path).st_mtime
        except Exception:
            return None
        old_time = self.mtimes.get(file_path, 0)
        if mtime > old_time:
            return None
        return self.cached_get(file_path)

    def cached_get(self, file_path):
        return self.data.get(file_path)

    def set(self, file_path, source):
        self.data[file_path] = source
        self.mtimes[file_path] = os.stat(file_path).st_mtime


class HashableCache(InnerCache, ReloadableMixin):
    def __init__(self, cache_interface):
        super(HashableCache, self).__init__(cache_interface)
        self.hashes = {}

    def reloader_get(self, name, source):
        hashed = make_hash(source)
        if self.hashes.get(name) != hashed:
            return None
        return self.cached_get(name, source)

    def cached_get(self, name, source):
        return self.data.get(name)

    def set(self, name, source):
        self.data[name] = source
        if self.cache.changes:
            self.hashes[name] = make_hash(source)


class PrerenderCache(HashableCache):
    pass


class ParserCache(HashableCache):
    def __init__(self, cache_interface):
        super(ParserCache, self).__init__(cache_interface)
        self.cdata = {}
        self.paths = {}
        self.dependencies = {}

    def _expired_dependency(self, path, name):
        tpath, tname = self.cache.templater.preload(path, name)
        file_path = os.path.join(tpath, tname)
        if os.stat(file_path).st_mtime != self.cache.load.mtimes[file_path]:
            return True
        return False

    def reloader_get(self, name, source):
        hashed = make_hash(source)
        if self.hashes.get(name) != hashed:
            return None, None
        for dep_name in self.dependencies[name]:
            if self._expired_dependency(self.paths[name], dep_name):
                return None, None
        return self.cached_get(name, source)

    def cached_get(self, name, source):
        return self.data.get(name), self.cdata.get(name)

    def set(self, path, name, source, compiled, content, dependencies):
        self.paths[name] = path
        self.data[name] = compiled
        self.cdata[name] = content
        if self.cache.changes:
            self.hashes[name] = make_hash(source)
            self.dependencies[name] = dependencies
