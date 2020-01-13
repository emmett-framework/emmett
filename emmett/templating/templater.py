# -*- coding: utf-8 -*-
"""
    emmett.templating.templater
    ---------------------------

    Provides the Emmett implementation for Renoir engine.

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

from renoir import Renoir

from .lexers import lexers


class Templater(Renoir):
    def __init__(self, **kwargs):
        kwargs['lexers'] = lexers
        super().__init__(**kwargs)

    def _set_reload(self, value):
        self.cache.changes = value
        self.cache.load._configure()
        self.cache.prerender._configure()
        self.cache.parse._configure()

    def _set_encoding(self, value):
        self.encoding = value

    def _set_escape(self, value):
        self.escape = value
        self._configure()

    def _set_prettify(self, value):
        self.prettify = value
        self._configure()
