# -*- coding: utf-8 -*-
"""
    weppy.templating.helpers
    ------------------------

    Provides helpers for templating system.

    :copyright: (c) 2014-2018 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

import os
import traceback


class TemplateMissingError(Exception):
    def __init__(self, file_path):
        self.path = file_path
        self.message = "Template %s not found" % self.path
        super(TemplateMissingError, self).__init__()


class TemplateError(Exception):
    def __init__(self, message, file_path, lineno):
        super(TemplateError, self).__init__(message)
        self.message = message
        self.file_path = file_path
        if isinstance(lineno, tuple):
            lineno = lineno[0]
        self.lineno = lineno


class TemplateSyntaxError(Exception):
    def __init__(self, parser_ctx, exc_type, exc_value, tb):
        super(TemplateSyntaxError, self).__init__('invalid syntax')
        self._reference = TemplateReference(
            parser_ctx, exc_type, exc_value, tb)

    @property
    def file_path(self):
        return self._reference.file_path

    @property
    def lineno(self):
        return self._reference.lineno

    @property
    def message(self):
        location = 'File "%s", line %d' % (self.file_path, self.lineno)
        lines = [self.args[0], '  ' + location]
        return "\n".join(lines)


class TemplateReference(object):
    def __init__(self, parser_ctx, exc_type, exc_value, tb):
        self.parser_ctx = parser_ctx
        self.exc_type = exc_type
        self.exc_value = exc_value
        self.tb = tb
        if hasattr(exc_value, 'lineno'):
            writer_lineno = exc_value.lineno
        else:
            template_frame = traceback.extract_tb(tb, 2)[-1]
            writer_lineno = template_frame[1]
        self.lines = parser_ctx.content.reference()
        self.template, self.lineno = self.match_template(writer_lineno)

    @property
    def file_path(self):
        return os.path.join(self.parser_ctx.path, self.template)

    def match_template(self, writer_lineno):
        element = self.lines[writer_lineno - 1]
        try:
            reference = (element[0], element[1])
        except Exception:
            reference = (self.parser_ctx.name, ('<unknown>', 'unknown'))
        return reference[0], reference[1][0]
