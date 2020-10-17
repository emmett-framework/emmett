# -*- coding: utf-8 -*-
"""
    emmett.templating.templater
    ---------------------------

    Provides the Emmett implementation for Renoir engine.

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

import os

from functools import reduce
from typing import Optional, Tuple

from renoir import Renoir

from .lexers import lexers


class Templater(Renoir):
    def __init__(self, **kwargs):
        kwargs['lexers'] = lexers
        super().__init__(**kwargs)
        self._namespaces = {}

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

    def _set_indent(self, value):
        self.indent = value
        self._configure()

    def register_namespace(self, namespace: str, path: Optional[str] = None):
        path = path or self.path
        self._namespaces[namespace] = path

    def _get_namespace_path_elements(self, file_name: str) -> Tuple[str, str]:
        if ":" in file_name:
            namespace, file_name = file_name.split(":")
            path = self._namespaces.get(namespace, self.path)
        else:
            path = self.path
        return path, file_name

    def _preload(self, file_name: str):
        path, file_name = self._get_namespace_path_elements(file_name)
        file_extension = os.path.splitext(file_name)[1]
        return reduce(
            lambda args, loader: loader(args[0], args[1]),
            self.loaders.get(file_extension, []),
            (path, file_name)
        )

    def _no_preload(self, file_name):
        return self._get_namespace_path_elements(file_name)
