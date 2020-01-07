# -*- coding: utf-8 -*-
"""
    emmett.debug
    ------------

    Provides debugging utilities.

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

import inspect
import os
import sys
import traceback

from renoir import Renoir

from .utils import cachedprop


class Traceback:
    """Wraps a traceback."""

    def __init__(self, app, exc_type, exc_value, tb):
        self.app = app
        self.exc_type = exc_type
        self.exc_value = exc_value
        if not isinstance(exc_type, str):
            exception_type = exc_type.__name__
            if exc_type.__module__ not in (
                '__builtin__', 'builtins', 'exceptions'
            ):
                exception_type = exc_type.__module__ + '.' + exception_type
        else:
            exception_type = exc_type
        self.exception_type = exception_type

        self.frames = []
        while tb:
            self.frames.append(Frame(self.app, exc_type, exc_value, tb))
            tb = tb.tb_next

    @property
    def exception(self):
        """String representation of the exception."""
        buf = traceback.format_exception_only(self.exc_type, self.exc_value)
        return ''.join(buf).strip()

    def generate_plaintext_traceback(self):
        """Like the plaintext attribute but returns a generator"""
        yield u'Traceback (most recent call last):'
        for frame in self.frames:
            yield u'  File "%s", line %s, in %s' % (
                frame.filename,
                frame.lineno,
                frame.function_name
            )
            yield u'    ' + frame.current_line.strip()
        yield self.exception

    def generate_plain_tb_app(self):
        yield u'Traceback (most recent call last):'
        for frame in self.frames:
            if frame.is_in_app:
                yield u'  File "%s", line %s, in %s' % (
                    frame.filename,
                    frame.lineno,
                    frame.function_name
                )
                yield u'    ' + frame.current_line.strip()
        yield self.exception

    @property
    def full_tb(self):
        return u'\n'.join(self.generate_plaintext_traceback())

    @property
    def app_tb(self):
        return u'\n'.join(self.generate_plain_tb_app())


class Frame:
    """A single frame in a traceback."""

    def __init__(self, app, exc_type, exc_value, tb):
        self.app = app
        self.lineno = tb.tb_lineno
        self.function_name = tb.tb_frame.f_code.co_name
        self.locals = tb.tb_frame.f_locals
        self.globals = tb.tb_frame.f_globals

        fn = inspect.getsourcefile(tb) or inspect.getfile(tb)
        if fn[-4:] in ('.pyo', '.pyc'):
            fn = fn[:-1]
        # if it's a file on the file system resolve the real filename.
        if os.path.isfile(fn):
            fn = os.path.realpath(fn)
        self.filename = fn
        self.module = self.globals.get('__name__')
        self.code = tb.tb_frame.f_code

    @property
    def is_in_fw(self):
        fw_path = os.path.dirname(__file__)
        return self.filename[0:len(fw_path)] == fw_path

    @property
    def is_in_app(self):
        return self.filename[0:len(self.app.root_path)] == self.app.root_path

    @property
    def rendered_filename(self):
        if self.is_in_app:
            return self.filename[len(self.app.root_path) + 1:]
        if self.is_in_fw:
            return ''.join([
                "emmett.",
                self.filename[
                    len(os.path.dirname(__file__)) + 1:
                ].replace("/", ".").split(".py")[0]
            ])
        return self.filename

    @cachedprop
    def sourcelines(self):
        try:
            with open(self.filename, 'rb') as file:
                source = file.read().decode('utf8')
        except IOError:
            source = '<unavailable>'
        return source.splitlines()

    @property
    def sourceblock(self):
        lmax = self.lineno + 4
        return u'\n'.join(self.sourcelines[self.first_line_no - 1:lmax])

    @property
    def first_line_no(self):
        number = self.lineno > 5 and (self.lineno - 5) or 1
        if number > len(self.sourcelines):
            number = 1
        while not self.sourcelines[number - 1]:
            number += 1
            if number > len(self.sourcelines):
                break
        return number

    @property
    def current_line(self):
        try:
            return self.sourcelines[self.lineno - 1]
        except IndexError:
            return u''

    @cachedprop
    def render_locals(self):
        rv = dict()
        for k, v in self.locals.items():
            try:
                rv[k] = str(v)
            except Exception:
                rv[k] = '<unavailable>'
        return rv


debug_templater = Renoir(
    path=os.path.join(os.path.dirname(__file__), 'assets', 'debug')
)


def smart_traceback(app):
    exc_type, exc_value, tb = sys.exc_info()
    return Traceback(app, exc_type, exc_value, tb)


def debug_handler(tb):
    return debug_templater.render('view.html', {'tb': tb})
