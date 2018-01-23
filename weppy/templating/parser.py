# -*- coding: utf-8 -*-
"""
    weppy.templating.parser
    -----------------------

    Provides the templating parser.

    :copyright: (c) 2014-2018 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

import os
import re
import uuid
from collections import namedtuple
from .contents import (
    Node, NodeGroup, WriterNode, EscapeNode, HTMLNode, PrettyWriterNode,
    PrettyEscapeNode, PrettyHTMLNode, PrettyHTMLPreNode)
from .helpers import TemplateError
from .lexers import default_lexers


class Content(object):
    __slots__ = ('_contents')

    def __init__(self):
        self._contents = []

    def append(self, element):
        self._contents.append(element)

    def extend(self, *elements):
        for element in elements:
            self.append(element)

    def render(self, parser):
        return u''.join(
            element.__render__(parser) for element in self._contents)

    def reference(self):
        rv = []
        for element in self._contents:
            rv.extend(element.__reference__())
        return rv


ParsedLines = namedtuple('ParsedLines', ('start', 'end'))


class ParsingState(object):
    __slots__ = (
        '_id', 'name', 'source', 'elements', 'blocks', 'lines',
        'in_python_block', 'content', 'parent', 'settings', 'dependencies',
        'indent', 'new_line')

    def __init__(
        self, name, elements, in_python_block=False, parent=None, source=None,
        line_start=1, **settings
    ):
        self._id = uuid.uuid4().hex
        self.name = name
        self.elements = elements
        self.in_python_block = in_python_block
        self.parent = parent
        self.source = source
        self.lines = ParsedLines(line_start, line_start)
        self.settings = settings
        self.content = Content()
        self.blocks = {}
        self.dependencies = []
        self.indent = 0
        self.new_line = True

    def __call__(
        self, name=None, elements=None, in_python_block=None, parent=None,
        source=None, line_start=None, **kwargs
    ):
        name = name or self.name
        elements = self.elements if elements is None else elements
        parent = parent or self
        source = source or parent.source
        settings = dict(**self.settings)
        if in_python_block is None:
            self.swap_block_type()
            in_python_block = parent.in_python_block
            line_start = parent.lines.end if line_start is None else line_start
            settings['isolated_pyblockstate'] = False
        else:
            line_start = 1 if line_start is None else line_start
            settings['isolated_pyblockstate'] = True
        if kwargs:
            settings.update(kwargs)
        return self.__class__(
            name, elements, in_python_block, parent, source, line_start,
            **settings)

    def swap_block_type(self):
        self.in_python_block = not self.in_python_block

    def update_lines_count(self, additional_lines, offset=None):
        start = self.lines.end if offset is None else offset
        self.lines = self.lines._replace(
            start=start, end=start + additional_lines)

    def __getattr__(self, name):
        return self.settings.get(name)


class ParsingContext(object):
    def __init__(
        self, parser, name, text, scope, writer_node_cls, escape_node_cls,
        html_node_cls, htmlpre_node_cls
    ):
        self.parser = parser
        self.stack = []
        self.scope = scope
        self.state = ParsingState(
            name, self.parser._tag_split_text(text), source=name,
            isolated_pyblockstate=True)
        self.contents_map = {}
        self.blocks_tree = {}
        self._writer_node_cls = writer_node_cls
        self._escape_node_cls = escape_node_cls
        self._html_node_cls = html_node_cls
        self._htmlpre_node_cls = htmlpre_node_cls
        self._in_html_pre = False

    @property
    def name(self):
        return self.state.name

    @property
    def content(self):
        return self.state.content

    @property
    def elements(self):
        return self.state.elements

    def swap_block_type(self):
        return self.state.swap_block_type()

    def update_lines_count(self, *args, **kwargs):
        return self.state.update_lines_count(*args, **kwargs)

    def __call__(
        self, name=None, elements=None, in_python_block=None, **kwargs
    ):
        self.stack.append(self.state)
        self.state = self.state(
            name=name, elements=elements, in_python_block=in_python_block,
            **kwargs)
        return self

    def load(self, name, **kwargs):
        name, file_path, text = self.parser._get_file_text(self, name)
        self.state.dependencies.append(name)
        kwargs['source'] = file_path
        kwargs['in_python_block'] = False
        return self(
            name=name, elements=self.parser._tag_split_text(text), **kwargs)

    def end_current_step(self):
        self.state.elements = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            raise
        self.swap_block_type()
        deps = list(self.state.dependencies)
        blocks = self.state.blocks
        contents = list(self.content._contents)
        name = self.name
        lines = self.state.lines
        in_python_block = self.state.in_python_block
        isolated_pyblockstate = self.state.isolated_pyblockstate
        state_id = self.state._id
        self.state = self.stack.pop()
        node = self.node_group(contents)
        if not isolated_pyblockstate:
            self.state.in_python_block = in_python_block
            self.update_lines_count(
                lines.end - lines.start, offset=lines.end)
        self.blocks_tree.update(blocks)
        self.state.blocks[name] = state_id
        self.state.dependencies.extend(deps)
        self.contents_map[state_id] = node

    def python_node(self, value=None):
        node = Node(value, source=self.state.source, lines=self.state.lines)
        self.content.append(node)
        return node

    def variable(self, value=None, escape=True):
        node_cls = self._escape_node_cls if escape else self._writer_node_cls
        node = node_cls(
            value, indent=self.state.indent, new_line=self.state.new_line,
            source=self.state.source, lines=self.state.lines)
        self.content.append(node)
        return node

    def node_group(self, value=None):
        node = NodeGroup(value, indent=self.state.indent)
        self.content.append(node)
        return node

    def html(self, value):
        node_cls = (
            self._html_node_cls if not self._in_html_pre else
            self._htmlpre_node_cls)
        self.content.append(
            node_cls(
                value, indent=self.state.indent, new_line=self.state.new_line,
                source=self.state.source, lines=self.state.lines))

    def parse(self):
        while self.elements:
            element = self.elements.pop(0)
            if self.state.in_python_block:
                self.parser.parse_python_block(self, element)
            else:
                self.parser.parse_html_block(self, element)
            self.swap_block_type()


class TemplateParser(object):
    _nodes_cls = {
        'writer': WriterNode, 'escape': EscapeNode, 'html': HTMLNode,
        'htmlpre': HTMLNode}

    r_multiline = re.compile(r'(""".*?""")|(\'\'\'.*?\'\'\')', re.DOTALL)

    #: re-indentation rules
    re_auto_dedent = re.compile(
        '^(elif |else:|except:|except |finally:).*$', re.DOTALL)
    re_dedent = re.compile('^(return|continue|break|raise)( .*)?$', re.DOTALL)
    re_pass = re.compile('^pass( .*)?$', re.DOTALL)

    def __init__(
        self, templater, text, name="ParserContainer", scope={},
        path='templates/', writer=u'_writer_', lexers={},
        delimiters=('{{', '}}'), _super_nodes=[]
    ):
        self.templater = templater
        self.name = name
        self.text = text
        self.writer = writer
        self.path = path
        self.scope = scope
        #: lexers to use
        self.lexers = default_lexers
        self.lexers.update(lexers)
        #: configure delimiters
        self.delimiters = delimiters
        escaped_delimiters = (
            re.escape(delimiters[0]), re.escape(delimiters[1]))
        self.r_tag = re.compile(
            r'((?<!%s)%s.*?%s(?!%s))' % (
                escaped_delimiters[0][0:2], escaped_delimiters[0],
                escaped_delimiters[1], escaped_delimiters[1][-2:]), re.DOTALL)
        self.delimiters_len = (
            len(self.delimiters[0]), len(self.delimiters[1]))
        #: build content
        self.parse(text)

    def _tag_split_text(self, text):
        return self.r_tag.split(text.replace('\t', '    '))

    def _get_file_text(self, ctx, filename):
        #: remove quotation from filename string
        try:
            filename = eval(filename, self.scope)
        except Exception:
            raise TemplateError(
                'Invalid template filename', ctx.state.source, ctx.state.lines)
        #: get the file contents
        tpath, tname = self.templater.preload(self.path, filename)
        file_path = os.path.join(tpath, tname)
        try:
            text = self.templater.load(file_path)
        except Exception:
            raise TemplateError(
                'Unable to open included view file',
                ctx.state.source, ctx.state.lines)
        text = self.templater.prerender(text, file_path)
        return filename, file_path, text

    def parse_html_block(self, ctx, element):
        lines = element.split("\n")
        ctx.update_lines_count(len(lines) - 1)
        new_lines = [line for line in lines if line]
        if new_lines:
            ctx.html('\n'.join(new_lines))

    def _get_python_block_text(self, element):
        return element[self.delimiters_len[0]:-self.delimiters_len[1]].strip()

    def _parse_python_line(self, ctx, line):
        #: get line components for lexers
        if line.startswith('='):
            lex, value = '=', line[1:].strip()
        else:
            v = line.split(' ', 1)
            if len(v) == 1:
                lex = v[0]
                value = u''
            else:
                lex = v[0]
                value = v[1]
        #: use appropriate lexer if available for current lex
        lexer = self.lexers.get(lex)
        if lexer and not value.startswith('='):
            lexer(ctx, value=value)
            return
        #: otherwise add as a python node
        ctx.python_node(line)

    def parse_python_block(self, ctx, element):
        #: get rid of delimiters
        text = self._get_python_block_text(element)
        if not text:
            return
        ctx.update_lines_count(len(text.split('\n')) - 1)
        #: escape new lines on comment blocks
        text = re.sub(self.r_multiline, _escape_newlines, text)
        #: parse block lines
        lines = text.split('\n')
        for line in lines:
            self._parse_python_line(ctx, line.strip())

    def _build_ctx(self, text):
        return ParsingContext(
            self, self.name, text, self.scope, self._nodes_cls['writer'],
            self._nodes_cls['escape'], self._nodes_cls['html'],
            self._nodes_cls['htmlpre'])

    def parse(self, text):
        ctx = self._build_ctx(text)
        ctx.parse()
        self.content = ctx.content
        self.dependencies = list(set(ctx.state.dependencies))

    def reindent(self, text):
        lines = text.split(u'\n')
        new_lines = []
        indent = 0
        dedented = 0
        #: parse lines
        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                continue
            #: apply auto dedenting
            if TemplateParser.re_auto_dedent.match(line):
                indent = indent + dedented - 1
            dedented = 0
            #: apply indentation
            indent = max(indent, 0)
            new_lines.append(u' ' * (4 * indent) + line)
            #: dedenting on `pass`
            if TemplateParser.re_pass.match(line):
                indent -= 1
            #: implicit dedent on specific commands
            if TemplateParser.re_dedent.match(line):
                dedented = 1
                indent -= 1
            #: indenting on lines ending with `:`
            if line.endswith(u':') and not line.startswith(u'#'):
                indent += 1
        #: handle indentation errors
        if indent > 0:
            raise TemplateError(
                'missing "pass" in view', self.name, 1)
        elif indent < 0:
            raise TemplateError(
                'too many "pass" in view', self.name, 1)
        #: rebuild text
        return u'\n'.join(new_lines)

    def render(self):
        return self.reindent(self.content.render(self))


class PrettyTemplateParser(TemplateParser):
    _nodes_cls = {
        'writer': PrettyWriterNode,
        'escape': PrettyEscapeNode,
        'html': PrettyHTMLNode,
        'htmlpre': PrettyHTMLPreNode}

    r_wspace = re.compile("^( *)")

    @staticmethod
    def _check_html_pre(ctx, line):
        if not ctx._in_html_pre and '<pre' in line and '</pre>' not in line:
            return True, False
        if ctx._in_html_pre and '</pre>' in line:
            return False, True
        return False, False

    @staticmethod
    def _start_html_pre(ctx, start):
        if start:
            ctx._in_html_pre = True

    @staticmethod
    def _end_html_pre(ctx, end):
        if end:
            ctx._in_html_pre = False

    def parse_html_block(self, ctx, element):
        lines = element.split("\n")
        ctx.update_lines_count(len(lines) - 1)
        #: remove empty lines if needed
        removed_last_line = False
        if not lines[0]:
            lines.pop(0)
            ctx.state.new_line = True
        if lines and not lines[-1]:
            lines.pop()
            removed_last_line = True
        #: process lines
        line = None
        for line in lines:
            empty_line = not line
            indent = len(self.r_wspace.search(line).group(0))
            start_pre, end_pre = self._check_html_pre(ctx, line)
            self._end_html_pre(ctx, end_pre)
            line = line[indent:]
            ctx.state.indent = indent
            if line or empty_line:
                ctx.html(line)
            self._start_html_pre(ctx, start_pre)
            ctx.state.new_line = True
        #: set correct `new_line` state depending on last line
        if line and not removed_last_line:
            ctx.state.new_line = False
        else:
            ctx.state.new_line = True


def _escape_newlines(re_val):
    #: take the entire match and replace newlines with escaped newlines
    return re_val.group(0).replace('\n', '\\n')
