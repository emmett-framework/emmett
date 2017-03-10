# -*- coding: utf-8 -*-
"""
    weppy.templating.helpers
    ------------------------

    Provides helpers for templating system.

    :copyright: (c) 2014-2017 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

import os
import traceback
from .contents import BlockNode


class TemplateMissingError(Exception):
    def __init__(self, tpath, filename):
        self.path = tpath
        self.template = filename
        message = "Template %s not found" % self.template
        Exception.__init__(self, message)


class TemplateError(Exception):
    def __init__(self, tpath, message, filename, lineno):
        Exception.__init__(self, message)
        self.path = tpath
        self.template = filename
        if isinstance(lineno, tuple):
            lineno = lineno[0]
        self.lineno = lineno

    @property
    def file_path(self):
        return os.path.join(self.path, self.template)


class TemplateReference(object):
    def __init__(self, parserdata, code, exc_type, exc_value, tb):
        self.parser = parserdata
        self.exc_type = exc_type
        self.exc_value = exc_value
        self.tb = tb
        if hasattr(exc_value, 'lineno'):
            dummy_lineno = exc_value.lineno
        else:
            template_frame = traceback.extract_tb(tb, 2)[-1]
            dummy_lineno = template_frame[1]
        self.lines = self.get_template_reference(parserdata.content,
                                                 parserdata.blocks)
        self.template, self.lineno = self.match_template(dummy_lineno)

    @property
    def file_path(self):
        return os.path.join(self.parser.path, self.template)

    @property
    def message(self):
        location = 'File "%s", line %d' % (self.file_path, self.lineno)
        lines = [self.args[0], '  ' + location]
        return "\n".join(lines)

    def __str__(self):
        return str(self.exc_value)

    @staticmethod
    def get_template_reference(content, blocks):
        lines = []
        for node in content.nodes:
            if isinstance(node, BlockNode):
                if node.name in blocks:
                    lines += TemplateReference.get_template_reference(
                        blocks[node.name], blocks)
                else:
                    lines += TemplateReference.get_template_reference(node,
                                                                      blocks)
            else:
                node_lines = node._rendered_lines()
                if len(node_lines) == node.lines[1] - node.lines[0] + 1:
                    linenos = [(i, i + 1) for i in range(node.lines[0],
                                                         node.lines[1] + 1)]
                else:
                    linenos = [(node.lines[0], node.lines[1])
                               for i in range(0, len(node_lines))]
                for l in range(0, len(node_lines)):
                    lines.append((node.template, linenos[l]))
        return lines

    def match_template(self, dummy_lineno):
        try:
            reference = self.lines[dummy_lineno - 1]
        except:
            reference = (self.parser.name, ('<unknown>', 'unknown'))
        return reference[0], reference[1][0]
