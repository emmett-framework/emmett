# -*- coding: utf-8 -*-
"""
    weppy.validators.basic
    ----------------------

    Provide basic validators.

    :copyright: (c) 2015 by Giovanni Barillari

    Based on the web2py's validators (http://www.web2py.com)
    :copyright: (c) by Massimo Di Pierro <mdipierro@cs.depaul.edu>

    :license: LGPLv3 (http://www.gnu.org/licenses/lgpl.html)
"""

import re
from cgi import FieldStorage
from os import SEEK_END, SEEK_SET
from .helpers import translate, is_empty


class Validator(object):
    def formatter(self, value):
        return value

    def __call__(self, value):
        raise NotImplementedError
        return value, None


class _is(Validator):
    rule = None
    message = "Invalid value"

    def __init__(self, message=None):
        if message:
            self.message = message

    def __call__(self, value):
        if self.rule is None or \
                (self.rule is not None and self.rule.match(str(value))):
            return self.check(value)
        return value, translate(self.message)

    def check(self, value):
        return value, None


class _options(Validator):
    pass


class _not(Validator):
    def __init__(self, validators, message="value not allowed"):
        if not isinstance(validators, (list, tuple)):
            validators = [validators]
        self.conditions = validators
        self.message = message

    def __call__(self, value):
        val = value
        for condition in self.conditions:
            value, error = condition(value)
            if error is None:
                return val, self.message
        return value, None


class isntEmpty(Validator):
    def __init__(self, error_message='Enter a value', empty_regex=None):
        self.error_message = error_message
        if empty_regex is not None:
            self.empty_regex = re.compile(empty_regex)
        else:
            self.empty_regex = None

    def __call__(self, value):
        value, empty = is_empty(value, empty_regex=self.empty_regex)
        if empty:
            return value, translate(self.error_message)
        return value, None


class isEmptyOr(Validator):
    def __init__(self, other, null=None, empty_regex=None):
        (self.other, self.null) = (other, null)
        if empty_regex is not None:
            self.empty_regex = re.compile(empty_regex)
        else:
            self.empty_regex = None
        if hasattr(other, 'multiple'):
            self.multiple = other.multiple
        if hasattr(other, 'options'):
            self.options = self._options

    def _options(self):
        options = self.other.options()
        if (not options or options[0][0] != '') and not self.multiple:
            options.insert(0, ('', ''))
        return options

    def set_self_id(self, id):
        if isinstance(self.other, (list, tuple)):
            for item in self.other:
                if hasattr(item, 'set_self_id'):
                    item.set_self_id(id)
        else:
            if hasattr(self.other, 'set_self_id'):
                self.other.set_self_id(id)

    def __call__(self, value):
        value, empty = is_empty(value, empty_regex=self.empty_regex)
        if empty:
            return (self.null, None)
        if isinstance(self.other, (list, tuple)):
            error = None
            for item in self.other:
                value, error = item(value)
                if error:
                    break
            return value, error
        else:
            return self.other(value)

    def formatter(self, value):
        if hasattr(self.other, 'formatter'):
            return self.other.formatter(value)
        return value


class Equals(Validator):
    def __init__(self, expression, message='No match'):
        self.expression = expression
        self.message = message

    def __call__(self, value):
        if value == self.expression:
            return (value, None)
        return value, translate(self.message)


class Matches(Validator):
    """The argument of Matches is a regular expression."""

    def __init__(self, expression, message='Invalid expression', strict=False,
                 search=False, extract=False, is_unicode=False):
        if strict or not search:
            if not expression.startswith('^'):
                expression = '^(%s)' % expression
        if strict:
            if not expression.endswith('$'):
                expression = '(%s)$' % expression
        if is_unicode:
            if not isinstance(expression, unicode):
                expression = expression.decode('utf8')
            self.regex = re.compile(expression, re.UNICODE)
        else:
            self.regex = re.compile(expression)
        self.message = message
        self.extract = extract
        self.is_unicode = is_unicode

    def __call__(self, value):
        if self.is_unicode and not isinstance(value, unicode):
            match = self.regex.search(str(value).decode('utf8'))
        else:
            match = self.regex.search(str(value))
        if match is not None:
            return (self.extract and match.group() or value, None)
        return value, translate(self.message)


class hasLength(Validator):
    """
    Checks if length of field's value fits between given boundaries. Works
    for both text and file inputs.

    Args:
        maxsize: maximum allowed length / size
        minsize: minimum allowed length / size
    """

    def __init__(self, maxsize=255, minsize=0,
                 message='Enter from %(min)g to %(max)g characters'):
        self.maxsize = maxsize
        self.minsize = minsize
        self.message = message

    def __call__(self, value):
        if value is None:
            length = 0
            if self.minsize <= length <= self.maxsize:
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
            if self.minsize <= length <= self.maxsize:
                return (value, None)
        elif isinstance(value, str):
            try:
                lvalue = len(value.decode('utf8'))
            except:
                lvalue = len(value)
            if self.minsize <= lvalue <= self.maxsize:
                return (value, None)
        elif isinstance(value, unicode):
            if self.minsize <= len(value) <= self.maxsize:
                return (value.encode('utf8'), None)
        elif isinstance(value, (tuple, list)):
            if self.minsize <= len(value) <= self.maxsize:
                return (value, None)
        elif self.minsize <= len(str(value)) <= self.maxsize:
            return (str(value), None)
        return (value, translate(self.message)
                % dict(min=self.minsize, max=self.maxsize))
