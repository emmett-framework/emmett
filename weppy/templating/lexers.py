# -*- coding: utf-8 -*-
"""
    weppy.templating.lexers
    -----------------------

    Provides the default lexers for templating parsing
    (using the same logic applied for extensions).

    :copyright: (c) 2014-2018 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

from .._compat import to_unicode
from ..expose import Expose, url
from ..extensions import TemplateLexer


class WeppyLexer(TemplateLexer):
    evaluate_value = False

    def __init__(self):
        pass


class VariableLexer(WeppyLexer):
    def process(self, ctx, value):
        #: insert a variable in the template
        ctx.variable(value)


class BlockLexer(WeppyLexer):
    def process(self, ctx, value):
        #: create a new stack element with name
        with ctx(value):
            ctx.parse()


class EndLexer(WeppyLexer):
    def process(self, ctx, value):
        #: we are done with this node, move up in the stack
        ctx.end_current_step()


class SuperLexer(WeppyLexer):
    def process(self, ctx, value):
        #: create a node for later injection by super block
        target_block = value if value else ctx.name
        node = ctx.node_group()
        ctx.state.injections[target_block] = node


class IncludeLexer(WeppyLexer):
    def process(self, ctx, value):
        #: if we have a value, just add the new content
        if value:
            with ctx.load(value):
                ctx.parse()
                included_id = ctx.state._id
        #: otherwise, inject in the extended node
        else:
            extend_src = ctx.state.extend_map[ctx.state.source]
            extend_src.swap_block_type()
            with ctx(
                '__include__' + extend_src._id,
                extend_src.elements,
                in_python_block=extend_src.in_python_block,
                source=extend_src.source,
                line_start=extend_src.lines.end
            ):
                ctx.parse()
                extend_src.update_lines_count(
                    ctx.state.lines.end - ctx.state.lines.start)
                included_id = ctx.state._id
        ctx.contents_map[included_id].increment_children_indent(
            ctx.state.indent)


class ExtendLexer(WeppyLexer):
    def process(self, ctx, value):
        #: extend the proper template
        with ctx.load(
            value, extend_map=ctx.state.extend_map or {}, injections={}
        ):
            ctx.state.extend_map[ctx.state.source] = ctx.state.parent
            ctx.parse()
            self.inject_content_in_children(ctx)
            self.replace_extended_blocks(ctx)

    def inject_content_in_children(self, ctx):
        for key, node in ctx.state.injections.items():
            #: get the content to inject
            src = ctx.contents_map[ctx.state.blocks[key]]
            original_indent = src.indent
            #: align src indent with the destination
            src.change_indent(node.indent)
            node.value = list(src.value)
            #: restore the original indent on the block
            src.indent = original_indent

    def replace_extended_blocks(self, ctx):
        for key in set(ctx.state.blocks.keys()) & set(ctx.blocks_tree.keys()):
            #: get destination and source blocks
            dst = ctx.state.blocks[key]
            src = ctx.blocks_tree[key]
            #: update the source indent with the destination one
            ctx.contents_map[src].change_indent(ctx.contents_map[dst].indent)
            ctx.contents_map[dst].value = list(ctx.contents_map[src].value)
            #: cleanup
            ctx.contents_map[src].value = []
            del ctx.contents_map[src]
            del ctx.blocks_tree[key]


class HelpersLexer(WeppyLexer):
    helpers = [
        '<script type="text/javascript" ' +
        'src="{}/__weppy__/jquery.min.js"></script>',
        '<script type="text/javascript" ' +
        'src="{}/__weppy__/helpers.js"></script>']

    def process(self, ctx, value):
        for helper in self.helpers:
            ctx.html(helper.format(Expose._prefix_main))


class MetaLexer(WeppyLexer):
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


class StaticLexer(WeppyLexer):
    evaluate_value = True

    def process(self, ctx, value):
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
            ctx.html(s)


default_lexers = {
    '=': VariableLexer(),
    'block': BlockLexer(),
    'end': EndLexer(),
    'super': SuperLexer(),
    'include': IncludeLexer(),
    'extend': ExtendLexer(),
    'include_helpers': HelpersLexer(),
    'include_meta': MetaLexer(),
    'include_static': StaticLexer()
}
