# -*- coding: utf-8 -*-
"""
    weppy.extensions
    ----------------

    Provides base classes to create extensions.

    :copyright: (c) 2015 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""


class Extension(object):
    namespace = None

    def __init__(self, app, env, config):
        self.app = app
        self.env = env
        self.config = config

    def on_load(self):
        pass


class TemplateExtension(object):
    namespace = None
    file_extension = None
    lexers = {}

    def __init__(self, env, config):
        self.env = env
        self.config = config

    def preload(self, path, name):
        return path, name

    def preprocess(self, source, name):
        return source


class TemplateLexer(object):
    def __init__(self, extension):
        self.ext = extension

    def __call__(self, parser=None, value=None, top=None, stack=None):
        self.parser = parser
        self.process(value, top, stack)

    def write(self, line, escape=False):
        if escape:
            s = "\n%s('%s', escape=True)" % (self.writer, line)
        else:
            s = "\n%s('%s', escape=False)" % (self.writer, line)
        return s

    def process(self, value, top, stack):
        pass
