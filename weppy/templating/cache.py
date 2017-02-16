# -*- coding: utf-8 -*-
"""
    weppy.templating.cache
    ----------------------

    Provides cache for templating system.

    :copyright: (c) 2014-2017 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

import os
import hashlib
from .._compat import iteritems, to_bytes
from ..utils import cachedprop


def make_md5(value):
    return hashlib.md5(to_bytes(value)).hexdigest()[:8]


class TemplaterCache(object):
    def __init__(self, app, templater):
        self.app = app
        self.templater = templater
        self.tpath = app.template_path
        self.preload = PreloaderCache(self)
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


class PreloaderCache(InnerCache):
    def get(self, path, name):
        return self.data.get((path, name))

    def set(self, path, name, val):
        self.data[(path, name)] = val


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
        except:
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

    def reloader_get(self, filename, source):
        hashed = make_md5(source)
        if self.hashes.get(filename) != hashed:
            return None
        return self.cached_get(filename, source)

    def cached_get(self, filename, source):
        return self.data.get(filename)

    def set(self, filename, source):
        self.data[filename] = source
        if self.cache.changes:
            self.hashes[filename] = make_md5(source)


class PrerenderCache(HashableCache):
    pass


class ParserCache(HashableCache):
    def __init__(self, cache_interface):
        super(ParserCache, self).__init__(cache_interface)
        self.pdata = {}
        self.dependencies = {}

    def _fetch_dependency_source(self, tpath, tname):
        tsource = self.cache.templater.load(tpath, tname)
        return self.cache.templater.prerender(tsource, tname)

    def reloader_get(self, filename, source):
        hashed = make_md5(source)
        if self.hashes.get(filename) != hashed:
            return None, None
        for iname, (ipath, ihash) in iteritems(self.dependencies[filename]):
            hashed = make_md5(self._fetch_dependency_source(ipath, iname))
            if ihash != hashed:
                return None, None
        return self.cached_get(filename, source)

    def cached_get(self, filename, source):
        return self.data.get(filename), self.pdata.get(filename)

    def set(self, filename, source, compiled, pdata, included):
        self.data[filename] = compiled
        self.pdata[filename] = pdata
        if self.cache.changes:
            self.hashes[filename] = make_md5(source)
            self.dependencies[filename] = {}
            for ipath, iname, isource in included:
                self.dependencies[filename][iname] = (ipath, make_md5(isource))
