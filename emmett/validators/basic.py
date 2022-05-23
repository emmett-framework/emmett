# -*- coding: utf-8 -*-
"""
    emmett.validators.basic
    -----------------------

    Provide basic validators.

    :copyright: 2014 Giovanni Barillari

    Based on the web2py's validators (http://www.web2py.com)
    :copyright: (c) by Massimo Di Pierro <mdipierro@cs.depaul.edu>

    :license: LGPLv3 (http://www.gnu.org/licenses/lgpl.html)
"""

import re

from cgi import FieldStorage
from functools import reduce
from os import SEEK_END, SEEK_SET

# TODO: check unicode conversions
from .._shortcuts import to_unicode
from .helpers import translate, is_empty


class Validator:
    message = "Invalid value"

    def __init__(self, message=None):
        self.message = message or self.message

    def formatter(self, value):
        return value

    def __call__(self, value):
        raise NotImplementedError


class ParentValidator(Validator):
    def __init__(self, children, message=None):
        super().__init__(message=message)
        if not isinstance(children, (list, tuple)):
            children = [children]
        self.children = children

    def formatter(self, value):
        return reduce(
            lambda formatted_val, child: child.formatter(formatted_val),
            self.children,
            value
        )

    def __call__(self, value):
        raise NotImplementedError


class _is(Validator):
    message = "Invalid value"
    rule = None

    def __call__(self, value):
        if (
            self.rule is None or (
                self.rule is not None and
                self.rule.match(to_unicode(value) or '')
            )
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
        super().__init__(children, message=message)
        self.value = value

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
        super().__init__(message=message)
        self.empty_regex = re.compile(empty_regex) if empty_regex is not None else None

    def __call__(self, value):
        _, empty = is_empty(value, empty_regex=self.empty_regex)
        if empty:
            return None, None
        return value, translate(self.message)


class isntEmpty(isEmpty):
    message = "Cannot be empty"

    def __call__(self, value):
        newval, empty = is_empty(value, empty_regex=self.empty_regex)
        if empty:
            return newval, translate(self.message)
        return value, None


class isEmptyOr(ParentValidator):
    def __init__(self, children, empty_regex=None, message=None):
        super().__init__(children, message=message)
        self.empty_regex = re.compile(empty_regex) if empty_regex is not None else None
        for child in self.children:
            if hasattr(child, 'multiple'):
                self.multiple = child.multiple
                break
        for child in self.children:
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
    message = "No match"

    def __init__(self, expression, message=None):
        super().__init__(message=message)
        self.expression = expression

    def __call__(self, value):
        if value == self.expression:
            return (value, None)
        return value, translate(self.message)


class Matches(Validator):
    message = "Invalid expression"

    def __init__(
        self, expression, strict=False, search=False, extract=False, message=None
    ):
        super().__init__(message=message)
        if strict or not search:
            if not expression.startswith('^'):
                expression = '^(%s)' % expression
        if strict:
            if not expression.endswith('$'):
                expression = '(%s)$' % expression
        self.regex = re.compile(expression)
        self.extract = extract

    def __call__(self, value):
        match = self.regex.search(to_unicode(value) or '')
        if match is not None:
            return self.extract and match.group() or value, None
        return value, translate(self.message)


class hasLength(Validator):
    message = "Enter from {min} to {max} characters"

    def __init__(
        self, maxsize=256, minsize=0, include=(True, False), message=None
    ):
        super().__init__(message=message)
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
                return value, None
        elif getattr(value, '_emt_field_hashed_contents_', False):
            return value, None
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
                return value, None
        elif isinstance(value, bytes):
            try:
                lvalue = len(value.decode('utf8'))
            except Exception:
                lvalue = len(value)
            if self._between(lvalue):
                return value, None
        elif isinstance(value, str):
            if self._between(len(value)):
                return value, None
        elif isinstance(value, (tuple, list)):
            if self._between(len(value)):
                return value, None
        elif self._between(len(str(value))):
            return str(value), None
        return value, translate(self.message).format(min=self.minsize, max=self.maxsize)
