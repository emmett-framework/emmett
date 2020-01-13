# -*- coding: utf-8 -*-
"""
    emmett.language.helpers
    -----------------------

    Translation helpers.

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

import re

from severus.datastructures import Tstr as _Tstr

from ..datastructures import Accept


class Tstr(_Tstr):
    __slots__ = []

    def __getstate__(self):
        return {
            'text': self.text,
            'lang': self.lang,
            'args': self.args,
            'kwargs': self.kwargs
        }

    def __setstate__(self, state):
        self.text = state['text']
        self.lang = state['lang']
        self.args = state['args']
        self.kwargs = state['kwargs']

    def __getattr__(self, name):
        return getattr(str(self), name)

    def __json__(self):
        return str(self)


class LanguageAccept(Accept):
    regex_locale_delim = re.compile(r'[_-]')

    def _value_matches(self, value, item):
        def _normalize(language):
            return self.regex_locale_delim.split(language.lower())[0]
        return item == '*' or _normalize(value) == _normalize(item)
