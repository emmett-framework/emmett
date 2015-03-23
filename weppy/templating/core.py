# -*- coding: utf-8 -*-
"""
    weppy.templating.core
    ---------------------

    Provides the templating system for weppy.

    :copyright: (c) 2015 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

import os
import cgi
import sys
from .._compat import StringIO
from ..globals import current
from ..http import HTTP
from ..tags import asis
from ..helpers import load_component
from ..datastructures import sdict
from .parser import TemplateParser
from .cache import TemplaterCache
from .helpers import TemplateReference


class DummyResponse():
    def __init__(self):
        self.body = StringIO()

    def write(self, data, escape=True):
        body = None
        if not escape:
            body = str(data)
        else:
            if hasattr(data, 'xml') and callable(data.xml):
                try:
                    body = data.xml()
                except:
                    pass
        if body is None:
            # make it a string
            if not isinstance(data, (str, unicode)):
                data = str(data)
            elif isinstance(data, unicode):
                data = data.encode('utf8', 'xmlcharrefreplace')
            body = cgi.escape(data, True).replace("'", "&#x27;")
        self.body.write(body)


class Templater(object):
    def __init__(self, application):
        self.loaders = application.template_preloaders
        self.renders = application.template_extensions
        self.lexers = application.template_lexers
        self.cache = TemplaterCache(application)

    def preload(self, path, name):
        fext = os.path.splitext(name)[1]
        return reduce(lambda s, e: e.preload(s[0], s[1]),
                      self.loaders.get(fext, []), (path, name))

    def load(self, filename):
        try:
            file_obj = open(filename, 'rb')
            source = file_obj.read()
            file_obj.close()
        except IOError:
            raise RuntimeError('Unable to open template file: ' + filename)
        return source

    def prerender(self, source, filename):
        return reduce(lambda s, e: e.preprocess(s, filename),
                      self.renders, str(source))

    def inject(self, context):
        for extension in self.renders:
            extension.inject(context)

    def parse(self, path, filename, source, context):
        code, parserdata = self.cache.get(filename, source)
        if not code:
            parser = TemplateParser(self, source, name=filename,
                                    context=context, path=path)
            code = compile(str(parser), filename, 'exec')
            parserdata = sdict(content=parser.content,
                               blocks=parser.content.blocks)
            self.cache.set(filename, source, code, parserdata)
        return code, parserdata

    def render(self, source='', path=None, filename=None, context={}):
        if 'asis' not in context:
            context['asis'] = asis
        if 'load_component' not in context:
            context['load_component'] = load_component
        context['_DummyResponse_'] = DummyResponse()
        code, parserdata = self.parse(path, filename, source, context)
        self.inject(context)
        try:
            exec code in context
        except:
            from ..debug import make_traceback
            exc_info = sys.exc_info()
            try:
                parserdata.path = path
                parserdata.name = filename
                template_ref = TemplateReference(parserdata, code, exc_info[0],
                                                 exc_info[1], exc_info[2])
            except:
                template_ref = None
            context['__weppy_template__'] = template_ref
            make_traceback(exc_info, template_ref)
        return context['_DummyResponse_'].body.getvalue()


def render_template(application, filename):
    templater = Templater(application)
    tpath, tname = templater.preload(application.template_path, filename)
    filepath = os.path.join(tpath, tname)
    tsource = templater.load(filepath)
    tsource = templater.prerender(tsource, tname)
    from ..expose import url
    context = dict(current=current, url=url)
    return templater.render(tsource, tpath, tname, context)


def render(application, path, template, context):
    templater = Templater(application)
    tpath, tname = templater.preload(path, template)
    filepath = os.path.join(tpath, tname)
    if not os.path.exists(filepath):
        raise HTTP(404, body="Invalid view\n")
    tsource = templater.load(filepath)
    tsource = templater.prerender(tsource, tname)
    return templater.render(tsource, tpath, tname, context)
