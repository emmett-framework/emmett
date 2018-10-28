# -*- coding: utf-8 -*-
"""
    weppy.templating.core
    ---------------------

    Provides the templating system for weppy.

    :copyright: (c) 2014-2018 by Giovanni Barillari
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
from .parser import TemplateParser, PrettyTemplateParser
from .cache import TemplaterCache
from .helpers import (
    TemplateMissingError, TemplateError, TemplateSyntaxError,
    TemplateReference)


class Writer(object):
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

    def write(self, data):
        self.body.write(self._to_native(data))

    def _escape_data(self, data):
        body = None
        if hasattr(data, '__html__'):
            try:
                body = data.__html__()
            except Exception:
                pass
        if body is None:
            body = self._to_html(self._to_unicode(data))
        return body

    def escape(self, data):
        self.write(self._escape_data(data))


class IndentWriter(Writer):
    avoid_first_prepend = True

    def __init__(self):
        super(IndentWriter, self).__init__()
        self.write = (
            self._write_first if self.avoid_first_prepend else self._write)

    def _write_first(self, data, indent=0, prepend=''):
        self.body.write(' ' * indent)
        self.body.write(self._to_native(data))
        self.write = self._write

    def _write(self, data, indent=0, prepend=''):
        self.body.write(prepend)
        self.body.write(' ' * indent)
        self.body.write(self._to_native(data))

    def escape(self, data, indent=0, prepend=''):
        self.write(self._escape_data(data), indent, prepend)


class EscapeAll(object):
    @staticmethod
    def _to_html(data):
        return to_bytes(
            Writer._to_html(data), 'ascii', 'xmlcharrefreplace')


class EscapeAllWriter(EscapeAll, Writer):
    pass


class EscapeAllIndentWriter(EscapeAll, IndentWriter):
    pass


class Templater(object):
    _writer_cls = {
        'basic': {'common': Writer, 'all': EscapeAllWriter},
        'pretty': {'common': IndentWriter, 'all': EscapeAllIndentWriter}}

    def __init__(self, application):
        self.config = application.config
        self.loaders = application.template_preloaders
        self.renders = application.template_extensions
        self.lexers = application.template_lexers
        self.cache = TemplaterCache(application, self)

    @cachedprop
    def response_cls(self):
        _group_key = 'pretty' if self.config.templates_prettify else 'basic'
        _cls_group = self._writer_cls[_group_key]
        return _cls_group.get(
            self.config.templates_escape, _cls_group['common'])

    @cachedprop
    def parser_cls(self):
        return (
            PrettyTemplateParser if self.config.templates_prettify
            else TemplateParser)

    def _preload(self, path, name):
        fext = os.path.splitext(name)[1]
        return reduce(
            lambda s, e: e.preload(s[0], s[1]),
            self.loaders.get(fext, []), (path, name))

    def _no_preload(self, path, name):
        return path, name

    @cachedprop
    def preload(self):
        if self.loaders:
            return self._preload
        return self._no_preload

    def _load(self, file_path):
        with open(file_path, 'rb') as file_obj:
            source = to_unicode(
                file_obj.read(), charset=self.config.templates_encoding)
        return source

    def load(self, file_path):
        rv = self.cache.load.get(file_path)
        if not rv:
            try:
                rv = self._load(file_path)
            except Exception:
                raise TemplateMissingError(file_path)
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

    def parse(self, path, file_path, source, context):
        code, content = self.cache.parse.get(file_path, source)
        if not code:
            parser = self.parser_cls(
                self, source, name=file_path, scope=context, path=path,
                lexers=self.lexers)
            try:
                code = compile(
                    to_native(parser.render()), os.path.split(file_path)[-1],
                    'exec')
            except SyntaxError:
                exc_info = sys.exc_info()
                parser_ctx = sdict(
                    path=path, name=file_path, content=parser.content)
                raise TemplateSyntaxError(
                    parser_ctx, exc_info[0], exc_info[1], exc_info[2])
            content = parser.content
            self.cache.parse.set(
                path, file_path, source, code, content, parser.dependencies)
        return code, content

    def inject(self, context):
        for extension in self.renders:
            extension.inject(context)

    def _render(self, source='', path=None, file_path=None, context={}):
        if isinstance(context, sdict):
            context = dict(context)
        context['asis'] = context.get('asis', asis)
        context['load_component'] = context.get(
            'load_component', load_component)
        context['_writer_'] = self.response_cls()
        try:
            code, content = self.parse(path, file_path, source, context)
        except (TemplateError, TemplateSyntaxError):
            from ..debug import make_traceback
            make_traceback(sys.exc_info())
        self.inject(context)
        try:
            exec(code, context)
        except Exception:
            from ..debug import make_traceback
            exc_info = sys.exc_info()
            try:
                parser_ctx = sdict(path=path, name=file_path, content=content)
                template_ref = TemplateReference(
                    parser_ctx, exc_info[0], exc_info[1], exc_info[2])
            except Exception:
                template_ref = None
            context['__weppy_template__'] = template_ref
            make_traceback(exc_info, template_ref)
        return context['_writer_'].body.getvalue()

    def render(self, path, filename, context={}):
        tpath, tname = self.preload(path, filename)
        file_path = os.path.join(tpath, tname)
        tsource = self.load(file_path)
        tsource = self.prerender(tsource, file_path)
        return self._render(tsource, tpath, file_path, context)
