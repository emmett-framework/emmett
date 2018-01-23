# -*- coding: utf-8 -*-
"""
    weppy.templating.contents
    -------------------------

    Provides structures for templating system.

    :copyright: (c) 2014-2018 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

from .._compat import to_unicode
from ..datastructures import sdict


class Node(object):
    __slots__ = ('value', 'indent', 'new_line', 'source', 'lines')

    def __init__(
        self, value=None, indent=0, new_line=False, source=None, lines=None
    ):
        self.value = value
        self.indent = indent
        self.new_line = new_line
        self.source = source
        self.lines = lines or (None, None)

    def increment_indent(self, increment):
        self.indent += increment

    def change_indent(self, indent):
        self.indent = indent

    def __render__(self, parser):
        return u'\n' + to_unicode(self.value)

    def __reference__(self):
        return [(self.source, self.lines)]

    def _rendered_lines(self):
        return self.__render__(sdict(writer='w')).split(u"\n")[1:]


class NodeGroup(Node):
    def __init__(self, value=None, **kwargs):
        self.value = value or []
        super(NodeGroup, self).__init__(value, **kwargs)

    def increment_children_indent(self, increment):
        for element in self.value:
            element.increment_indent(increment)

    def increment_indent(self, increment):
        self.increment_children_indent(increment)
        self.indent += increment

    def change_indent(self, indent):
        diff = indent - self.indent
        self.increment_children_indent(diff)
        self.indent = indent

    def __render__(self, parser):
        return u''.join(element.__render__(parser) for element in self.value)

    def __reference__(self):
        rv = []
        for element in self.value:
            rv.extend(element.__reference__())
        return rv


class WriterNode(Node):
    _writer_method = 'write'
    _newline_val = {True: u', ' + to_unicode(repr('\n')), False: u''}

    def render_value(self):
        return self.value

    def __render__(self, parser):
        return u''.join([
            u'\n', parser.writer, u'.', self._writer_method, u'(',
            to_unicode(self.render_value()), u')'])


class EscapeNode(WriterNode):
    _writer_method = 'escape'


class HTMLNode(WriterNode):
    def render_value(self):
        return repr(self.value)


class PrettyMixin(object):
    def __render__(self, parser):
        return u''.join([
            u'\n', parser.writer, u'.', self._writer_method, u'(',
            to_unicode(self.render_value()), u', ',
            to_unicode(self.new_line and self.indent or 0),
            self._newline_val[self.new_line], u')'])


class PrettyWriterNode(PrettyMixin, WriterNode):
    pass


class PrettyEscapeNode(PrettyMixin, EscapeNode):
    pass


class PrettyHTMLNode(PrettyMixin, HTMLNode):
    pass


class PrettyHTMLPreNode(PrettyHTMLNode):
    def increment_indent(self, increment):
        return

    def change_indent(self, indent):
        return
