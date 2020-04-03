# -*- coding: utf-8 -*-
"""
    emmett.templating.lexers
    ------------------------

    Provides the Emmett lexers for Renoir engine.

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

from renoir import Lexer

from ..ctx import current
from ..routing.urls import url


class HelpersLexer(Lexer):
    helpers = [
        '<script type="text/javascript" ' +
        'src="{}/__emmett__/jquery.min.js"></script>',
        '<script type="text/javascript" ' +
        'src="{}/__emmett__/helpers.js"></script>'
    ]

    def process(self, ctx, value):
        for helper in self.helpers:
            ctx.html(helper.format(current.app._router_http._prefix_main))


class MetaLexer(Lexer):
    def process(self, ctx, value):
        ctx.python_node('for name, value in current.response._meta_tmpl():')
        ctx.variable(
            "'<meta name=\"%s\" content=\"%s\" />' % (name, value)",
            escape=False)
        ctx.python_node('pass')
        ctx.python_node(
            'for name, value in current.response._meta_tmpl_prop():')
        ctx.variable(
            "'<meta property=\"%s\" content=\"%s\" />' % (name, value)",
            escape=False)
        ctx.python_node('pass')


class StaticLexer(Lexer):
    evaluate = True

    def process(self, ctx, value):
        file_name = value.split("?")[0]
        surl = url('static', file_name)
        file_ext = file_name.rsplit(".", 1)[-1]
        if file_ext == 'js':
            s = u'<script type="text/javascript" src="%s"></script>' % surl
        elif file_ext == "css":
            s = u'<link rel="stylesheet" href="%s" type="text/css" />' % surl
        else:
            s = None
        if s:
            ctx.html(s)


lexers = {
    'include_helpers': HelpersLexer(),
    'include_meta': MetaLexer(),
    'include_static': StaticLexer()
}
