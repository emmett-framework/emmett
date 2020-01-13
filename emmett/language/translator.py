# -*- coding: utf-8 -*-
"""
    emmett.language.translator
    --------------------------

    Severus translator implementation for Emmett.

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

from __future__ import annotations

from typing import Optional
from severus.ctx import set_context
from severus.translator import Translator as _Translator

from ..ctx import current


class Translator(_Translator):
    __slots__ = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        set_context(self)

    def _update_config(self, default_language: str):
        self._default_language = default_language
        self._langmap.clear()
        self._languages.clear()
        self._build_languages()

    def _get_best_language(self, lang: Optional[str] = None) -> str:
        return self._langmap.get(
            lang or current.language, self._default_language
        )
