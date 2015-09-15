# -*- coding: utf-8 -*-
"""
    weppy.templating.lexers
    -----------------------

    Provides the default lexers for templating parsing
    (using the same logic applied for extensions).

    :copyright: (c) 2015 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

from .._compat import to_unicode
from ..extensions import TemplateLexer
from .contents import SuperNode, BlockNode


class WeppyLexer(TemplateLexer):
    evaluate_value = False

    def __init__(self):
        pass


class DefineLexer(WeppyLexer):
    def process(self, value):
        #: insert a variable in the template
        node = self.parser.create_node(value, self.parser._is_pre_extend)
        self.top.append(node)


class BlockLexer(WeppyLexer):
    def process(self, value):
        #: create a new node with name
        node = self.parser.create_block(
            value.strip(), self.parser._is_pre_extend)
        #: append this node to the active one
        self.top.append(node)
        #: add the node to the stack so anything after this gets added
        #  to this node. This allows us to "nest" nodes.
        self.stack.append(node)


class EndLexer(WeppyLexer):
    def process(self, value):
        #: we are done with this node, let's store the instance
        self.parser.blocks[self.top.name] = self.top
        #: and pop it
        self.stack.pop()


class SuperLexer(WeppyLexer):
    def process(self, value):
        #: get correct target name, if not provided assume the top block
        target_node = value if value else self.top.name
        #: create a SuperNode instance
        node = SuperNode(name=target_node,
                         pre_extend=self.parser._is_pre_extend)
        #: add new node to the super_nodes list
        self.parser.super_nodes.append(node)
        #: put the node into the tree
        self.top.append(node)


class IncludeLexer(WeppyLexer):
    def process(self, value):
        #: if we have a value, just call the parser function
        if value:
            self.parser.include(self.top, value)
        #: otherwise, make a temporary include node that the child node
        #  will know to hook into.
        else:
            include_node = BlockNode(
                name='__include__' + self.parser.name,
                pre_extend=self.parser._is_pre_extend,
                delimiters=self.parser.delimiters)
            self.top.append(include_node)


class ExtendLexer(WeppyLexer):
    def process(self, value):
        #: extend the proper template
        self.parser._needs_extend = value
        self.parser._is_pre_extend = False


class HelpersLexer(WeppyLexer):
    helpers = [
        '<script type="text/javascript" ' +
        'src="/__weppy__/jquery.min.js"></script>',
        '<script type="text/javascript" ' +
        'src="/__weppy__/helpers.js"></script>']

    def process(self, value):
        node = self.parser.create_htmlnode(
            u"\n".join(h for h in self.helpers), self.parser._is_pre_extend)
        self.top.append(node)


class MetaLexer(WeppyLexer):
    def process(self, value):
        if not value:
            value = u'current.response.get_meta()'
        node = self.parser.create_node(
            value, self.parser._is_pre_extend, writer_escape=False)
        self.top.append(node)


class StaticLexer(WeppyLexer):
    evaluate_value = True

    def process(self, value):
        from ..expose import url
        file_name = value.split("?")[0]
        surl = to_unicode(url('static', file_name))
        file_ext = file_name.rsplit(".", 1)[-1]
        if file_ext == 'js':
            s = u'<script type="text/javascript" src="%s"></script>' % surl
        elif file_ext == "css":
            s = u'<link rel="stylesheet" href="%s" type="text/css" />' % surl
        else:
            s = None
        if s:
            node = self.parser.create_htmlnode(s, self.parser._is_pre_extend)
            self.top.append(node)


default_lexers = {
    '=': DefineLexer(),
    'block': BlockLexer(),
    'end': EndLexer(),
    'super': SuperLexer(),
    'include': IncludeLexer(),
    'extend': ExtendLexer(),
    'include_helpers': HelpersLexer(),
    'include_meta': MetaLexer(),
    'include_static': StaticLexer()
}
