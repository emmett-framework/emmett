# -*- coding: utf-8 -*-
"""
    weppy.templating.core
    ---------------------

    Provides the templating system for weppy.

    :copyright: (c) 2014-2017 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

import os
import sys
from .._compat import StringIO, reduce, string_types, text_type, to_native, \
    to_unicode, to_bytes
from ..datastructures import sdict
from ..helpers import load_component
from ..html import asis, htmlescape
from ..utils import cachedprop
from .parser import TemplateParser
from .cache import TemplaterCache
from .helpers import TemplateMissingError, TemplateReference


class DummyResponse():
    def __init__(self):
        self.body = StringIO()

    @staticmethod
    def _to_html(data):
        return htmlescape(data)

    @staticmethod
    def _to_native(data):
        if not isinstance(data, text_type):
            data = to_unicode(data)
        return to_native(data)

    @staticmethod
    def _to_unicode(data):
        if not isinstance(data, string_types):
            return text_type(data)
        return to_unicode(data)

    def write(self, data, escape=True):
        body = None
        if escape:
            if hasattr(data, '__html__'):
                try:
                    body = to_native(data.__html__())
                except:
                    pass
            if body is None:
                body = self._to_native(self._to_html(self._to_unicode(data)))
        else:
            body = self._to_native(data)
        self.body.write(body)


class DummyResponseEscapeAll(DummyResponse):
    @staticmethod
    def _to_html(data):
        return to_bytes(
            DummyResponse._to_html(data), 'ascii', 'xmlcharrefreplace')


class Templater(object):
    _resp_cls = {'common': DummyResponse, 'all': DummyResponseEscapeAll}

    def __init__(self, application):
        self.config = application.config
        self.loaders = application.template_preloaders
        self.renders = application.template_extensions
        self.lexers = application.template_lexers
        self.cache = TemplaterCache(application, self)

    @cachedprop
    def response_cls(self):
        return self._resp_cls.get(
            self.config.templates_escape, self._resp_cls['common'])

    def _preload(self, path, name):
        fext = os.path.splitext(name)[1]
        return reduce(
            lambda s, e: e.preload(s[0], s[1]),
            self.loaders.get(fext, []), (path, name))

    def preload(self, path, name):
        rv = self.cache.preload.get(path, name)
        if not rv:
            rv = self._preload(path, name)
            self.cache.preload.set(path, name, rv)
        return rv

    def _load(self, file_path):
        file_obj = open(file_path, 'r')
        source = to_unicode(file_obj.read())
        file_obj.close()
        return source

    def load(self, path, filename):
        file_path = os.path.join(path, filename)
        rv = self.cache.load.get(file_path)
        if not rv:
            try:
                rv = self._load(file_path)
            except:
                raise TemplateMissingError(path, filename)
            self.cache.load.set(file_path, rv)
        return rv

    def _prerender(self, source, filename):
        return reduce(
            lambda s, e: e.preprocess(s, filename), self.renders, source)

    def prerender(self, source, filename):
        rv = self.cache.prerender.get(filename, source)
        if not rv:
            rv = self._prerender(source, filename)
            self.cache.prerender.set(filename, source)
        return rv

    def parse(self, path, filename, source, context):
        code, parserdata = self.cache.parse.get(filename, source)
        if not code:
            parser = TemplateParser(
                self, source, name=filename, context=context, path=path)
            code = compile(str(parser), filename, 'exec')
            parserdata = sdict(
                content=parser.content, blocks=parser.content.blocks)
            self.cache.parse.set(
                filename, source, code, parserdata, parser.included_templates)
        return code, parserdata

    def inject(self, context):
        for extension in self.renders:
            extension.inject(context)

    def _render(self, source='', path=None, filename=None, context={}):
        if isinstance(context, sdict):
            context = dict(context)
        context['asis'] = context.get('asis', asis)
        context['load_component'] = context.get(
            'load_component', load_component)
        context['_DummyResponse_'] = self.response_cls()
        code, parserdata = self.parse(path, filename, source, context)
        self.inject(context)
        try:
            exec(code, context)
        except:
            from ..debug import make_traceback
            exc_info = sys.exc_info()
            try:
                parserdata.path = path
                parserdata.name = filename
                template_ref = TemplateReference(
                    parserdata, code, exc_info[0], exc_info[1], exc_info[2])
            except:
                template_ref = None
            context['__weppy_template__'] = template_ref
            make_traceback(exc_info, template_ref)
        return context['_DummyResponse_'].body.getvalue()

    def render(self, path, filename, context={}):
        tpath, tname = self.preload(path, filename)
        tsource = self.load(tpath, tname)
        tsource = self.prerender(tsource, tname)
        return self._render(tsource, tpath, tname, context)
