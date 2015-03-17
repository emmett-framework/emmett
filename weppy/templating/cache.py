# -*- coding: utf-8 -*-
"""
    weppy.templating.cache
    ----------------------

    Provides cache for templating system.

    :copyright: (c) 2015 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

from .._compat import hashlib_md5


def make_md5(value):
    return hashlib_md5(value).hexdigest()[:8]


class TemplaterCache(object):
    data = {}
    pdata = {}
    hashes = {}

    def __init__(self, app):
        self.changes = app.debug or app.config.templates_auto_reload

    def get(self, filename, source):
        if self.changes:
            hashed = make_md5(source)
            if self.hashes.get(filename) != hashed:
                return None, None
        return self.data.get(filename), self.pdata.get(filename)

    def set(self, filename, source, compiled, pdata):
        self.data[filename] = compiled
        self.pdata[filename] = pdata
        if self.changes:
            self.hashes[filename] = make_md5(source)
