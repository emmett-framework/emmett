# -*- coding: utf-8 -*-
"""
    weppy.validators.basic
    ----------------------

    Provide basic validators.

    :copyright: (c) 2014-2017 by Giovanni Barillari

    Based on the web2py's validators (http://www.web2py.com)
    :copyright: (c) by Massimo Di Pierro <mdipierro@cs.depaul.edu>

    :license: LGPLv3 (http://www.gnu.org/licenses/lgpl.html)
"""

import re
from cgi import FieldStorage
from os import SEEK_END, SEEK_SET
from .._compat import text_type, to_unicode, to_native
from .helpers import translate, is_empty


class Validator(object):
    message = "Invalid value"

    def __init__(self, message=None):
        if message:
            self.message = message

    def formatter(self, value):
        return value

    def __call__(self, value):
        raise NotImplementedError
        return value, None


class ParentValidator(Validator):
    def __init__(self, children, message=None):
        Validator.__init__(self, message)
        if not isinstance(children, (list, tuple)):
            children = [children]
        self.children = children

    def formatter(self, value):
        for child in self.children:
            if hasattr(child, 'formatter') and child(value)[1] is not None:
                return child.formatter(value)
        return value


class _is(Validator):
    rule = None
    message = "Invalid value"

    def __call__(self, value):
        if (
            self.rule is None or (
                self.rule is not None and
                self.rule.match(to_native(to_unicode(value)) or ''))
        ):
            return self.check(value)
        return value, translate(self.message)

    def check(self, value):
        return value, None


class Not(ParentValidator):
    message = "Value not allowed"

    def __call__(self, value):
        val = value
        for child in self.children:
            value, error = child(value)
            if error is None:
                return val, translate(self.message)
        return value, None


class Any(ParentValidator):
    def __call__(self, value):
        for child in self.children:
            value, error = child(value)
            if error is None:
                break
        return value, error


class Allow(ParentValidator):
    def __init__(self, value, children, message=None):
        ParentValidator.__init__(self, children, message)
        self.value = value

    def formatter(self, value):
        return value

    def __call__(self, value):
        val = value
        comparing = self.value() if callable(self.value) else self.value
        if value is not comparing:
            for child in self.children:
                value, error = child(value)
                if error:
                    return val, error
        return value, None


class isEmpty(Validator):
    message = "No value allowed"

    def __init__(self, empty_regex=None, message=None):
        Validator.__init__(self, message)
        if empty_regex is not None:
            self.empty_regex = re.compile(empty_regex)
        else:
            self.empty_regex = None

    def __call__(self, value):
        value, empty = is_empty(value, empty_regex=self.empty_regex)
        if empty:
            return None, None
        return value, translate(self.message)


class isntEmpty(isEmpty):
    message = "Cannot be empty"

    def __call__(self, value):
        value, empty = is_empty(value, empty_regex=self.empty_regex)
        if empty:
            return value, translate(self.message)
        return value, None


class isEmptyOr(ParentValidator, isEmpty):
    def __init__(self, children, empty_regex=None, message=None):
        ParentValidator.__init__(self, children, message)
        isEmpty.__init__(self, empty_regex)
        for child in children:
            if hasattr(child, 'multiple'):
                self.multiple = child.multiple
                break
        for child in children:
            if hasattr(child, 'options'):
                self._options_ = child.options
                self.options = self._get_options_
                break

    def _get_options_(self):
        options = self._options_()
        if (not options or options[0][0] != '') and not self.multiple:
            options.insert(0, ('', ''))
        return options

    def __call__(self, value):
        value, empty = is_empty(value, empty_regex=self.empty_regex)
        if empty:
            return None, None
        error = None
        for child in self.children:
            value, error = child(value)
            if error:
                break
        return value, error


class Equals(Validator):
    message = 'No match'

    def __init__(self, expression, message=None):
        Validator.__init__(self, message)
        self.expression = expression

    def __call__(self, value):
        if value == self.expression:
            return (value, None)
        return value, translate(self.message)


class Matches(Validator):
    message = "Invalid expression"

    def __init__(self, expression, strict=False, search=False, extract=False,
                 message=None):
        Validator.__init__(self, message)
        if strict or not search:
            if not expression.startswith('^'):
                expression = '^(%s)' % expression
        if strict:
            if not expression.endswith('$'):
                expression = '(%s)$' % expression
        #if is_unicode:
        #    if not isinstance(expression, unicode):
        #        expression = expression.decode('utf8')
        #    self.regex = re.compile(expression, re.UNICODE)
        #else:
        self.regex = re.compile(expression)
        self.extract = extract
        #self.is_unicode = is_unicode

    def __call__(self, value):
        #if self.is_unicode and not isinstance(value, unicode):
        #    match = self.regex.search(str(value).decode('utf8'))
        #else:
        match = self.regex.search(to_native(to_unicode(value)) or '')
        if match is not None:
            return self.extract and match.group() or value, None
        return value, translate(self.message)


class hasLength(Validator):
    """
    Checks if length of field's value fits between given boundaries. Works
    for both text and file inputs.

    Args:
        maxsize: maximum allowed length / size
        minsize: minimum allowed length / size
    """
    message = 'Enter from %(min)g to %(max)g characters'

    def __init__(self, maxsize=256, minsize=0, include=(True, False),
                 message=None):
        Validator.__init__(self, message)
        self.maxsize = maxsize
        self.minsize = minsize
        self.inc = include

    def _between(self, value):
        if self.inc[0]:
            great = self.minsize <= value
        else:
            great = self.minsize < value
        if self.inc[1]:
            less = value <= self.maxsize
        else:
            less = value < self.maxsize
        return great and less

    def __call__(self, value):
        if value is None:
            length = 0
            if self._between(length):
                return (value, None)
        elif isinstance(value, FieldStorage):
            if value.file:
                value.file.seek(0, SEEK_END)
                length = value.file.tell()
                value.file.seek(0, SEEK_SET)
            elif hasattr(value, 'value'):
                val = value.value
                if val:
                    length = len(val)
                else:
                    length = 0
            if self._between(length):
                return (value, None)
        elif isinstance(value, bytes):
            try:
                lvalue = len(to_unicode(value))
            except:
                lvalue = len(value)
            if self._between(lvalue):
                return (value, None)
        elif isinstance(value, text_type):
            if self._between(len(value)):
                return (to_native(value), None)
        elif isinstance(value, (tuple, list)):
            if self._between(len(value)):
                return (value, None)
        elif self._between(len(str(value))):
            return (str(value), None)
        return (value, translate(self.message)
                % dict(min=self.minsize, max=self.maxsize))
