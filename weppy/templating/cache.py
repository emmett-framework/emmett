# -*- coding: utf-8 -*-
"""
    weppy.templating.cache
    ----------------------

    Provides cache for templating system.

    :copyright: (c) 2014-2016 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

import hashlib
from .._compat import iteritems, to_bytes
from ..utils import cachedprop


def make_md5(value):
    return hashlib.md5(to_bytes(value)).hexdigest()[:8]


class TemplaterCache(object):
    data = {}
    pdata = {}
    hashes = {}
    dependencies = {}

    def __init__(self, app, templater):
        self.app = app
        self.templater = templater
        self.tpath = app.template_path

    @cachedprop
    def changes(self):
        return self.app.debug or self.app.config.templates_auto_reload

    @cachedprop
    def get(self):
        if self.changes:
            return self.reloader_get
        return self.cached_get

    def _fetch_dependency_source(self, filename):
        tpath, tname = self.templater.preload(self.tpath, filename)
        tsource = self.templater.load(tpath, tname)
        return self.templater.prerender(tsource, tname)

    def reloader_get(self, filename, source):
        hashed = make_md5(source)
        if self.hashes.get(filename) != hashed:
            return None, None
        for iname, ihash in iteritems(self.dependencies[filename]):
            hashed = make_md5(self._fetch_dependency_source(iname))
            if ihash != hashed:
                return None, None
        return self.cached_get(filename, source)

    def cached_get(self, filename, source):
        return self.data.get(filename), self.pdata.get(filename)

    def set(self, filename, source, compiled, pdata, included):
        self.data[filename] = compiled
        self.pdata[filename] = pdata
        if self.changes:
            self.hashes[filename] = make_md5(source)
            self.dependencies[filename] = {}
            for iname, isource in included:
                self.dependencies[filename][iname] = make_md5(isource)
