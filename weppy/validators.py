# -*- coding: utf-8 -*-
"""
    weppy.validators
    ----------------

    Provide the validation tools for DAL.

    adapted from the original validators of web2py (http://www.web2py.com)

    :copyright: (c) by Massimo Di Pierro <mdipierro@cs.depaul.edu>
    :license: LGPLv3 (http://www.gnu.org/licenses/lgpl.html)
"""

import os
import re
import datetime
import time
import cgi
import urllib
import struct
import decimal
import unicodedata
import json

from ._compat import StringIO
from .security import simple_hash, uuid, DIGEST_ALG_BY_SIZE
from .globals import current

__all__ = [
    'anyOf',
    'Cleanup',
    'Crypt',
    'isAlphanumeric',
    'isDateInRange',
    'isDate',
    'isDatetimeInRange',
    'isDatetime',
    'isDecimalInRange',
    'isEmail',
    'isEmailList',
    'isEmptyOr',
    'isFloatInRange',
    'isImage',
    'inDb',
    'inSet',
    'isIntInRange',
    'isIPv4',
    'isIPv6',
    'isIP',
    'hasLength',
    'isListOf',
    'Lower',
    'Matches',
    'Equals',
    'isntEmpty',
    'notInDb',
    'Slug',
    'isStrong',
    'isTime',
    'FilenameMatches',
    'Upper',
    'isUrl',
    'isJSON'
]


def _translate(text):
    if text is None:
        return None
    elif isinstance(text, (str, unicode)):
        #if hasattr(current, 'T'):
        #    return str(current.T(text))
        return current.T(text)
    return str(text)


def _options_sorter(x, y):
    return (str(x[1]).upper() > str(y[1]).upper() and 1) or -1


class Validator(object):
    """
    Base class for all validators, mainly for documentation purposes.

    Validators are classes used to validate input fields (including forms
    generated from database tables).
    """

    def formatter(self, value):
        """
        For some validators returns a formatted version of value. Otherwise
        just returns the value.
        """
        return value

    def __call__(self, value):
        raise NotImplementedError
        return (value, None)


class Matches(Validator):
    """
    The argument of Matches is a regular expression.
    """

    def __init__(self, expression, error_message='Invalid expression',
                 strict=False, search=False, extract=False,
                 is_unicode=False):

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
        self.error_message = error_message
        self.extract = extract
        self.is_unicode = is_unicode

    def __call__(self, value):
        if self.is_unicode and not isinstance(value, unicode):
            match = self.regex.search(str(value).decode('utf8'))
        else:
            match = self.regex.search(str(value))
        if match is not None:
            return (self.extract and match.group() or value, None)
        return (value, _translate(self.error_message))


class Equals(Validator):
    def __init__(self, expression, error_message='No match'):
        self.expression = expression
        self.error_message = error_message

    def __call__(self, value):
        if value == self.expression:
            return (value, None)
        return (value, _translate(self.error_message))


class hasLength(Validator):
    """
    Checks if length of field's value fits between given boundaries. Works
    for both text and file inputs.

    Args:
        maxsize: maximum allowed length / size
        minsize: minimum allowed length / size
    """

    def __init__(self, maxsize=255, minsize=0,
                 error_message='Enter from %(min)g to %(max)g characters'):
        self.maxsize = maxsize
        self.minsize = minsize
        self.error_message = error_message

    def __call__(self, value):
        if value is None:
            length = 0
            if self.minsize <= length <= self.maxsize:
                return (value, None)
        elif isinstance(value, cgi.FieldStorage):
            if value.file:
                value.file.seek(0, os.SEEK_END)
                length = value.file.tell()
                value.file.seek(0, os.SEEK_SET)
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
        return (value, _translate(self.error_message)
                % dict(min=self.minsize, max=self.maxsize))


class isJSON(Validator):
    JSONErrors = (NameError, TypeError, ValueError, AttributeError,
                  KeyError)

    def __init__(self, error_message='Invalid json', native_json=False):
        self.native_json = native_json
        self.error_message = error_message

    def __call__(self, value):
        try:
            if self.native_json:
                json.loads(value)
                return (value, None)
            return (json.loads(value), None)
        except self.JSONErrors:
            return (value, _translate(self.error_message))

    def formatter(self, value):
        if value is None:
            return None
        return json.dumps(value)


class inSet(Validator):
    """
    Check that value is one of the given list or set.
    """

    def __init__(
        self,
        theset,
        labels=None,
        error_message='Value not allowed',
        multiple=False,
        zero='',
        sort=False,
    ):
        self.multiple = multiple
        if isinstance(theset, dict):
            self.theset = [str(item) for item in theset]
            self.labels = theset.values()
        elif theset and isinstance(theset, (tuple, list)) \
                and isinstance(theset[0], (tuple, list)) \
                and len(theset[0]) == 2:
            self.theset = [str(item) for item, label in theset]
            self.labels = [str(label) for item, label in theset]
        else:
            self.theset = [str(item) for item in theset]
            self.labels = labels
        self.error_message = error_message
        self.zero = zero
        self.sort = sort

    def options(self, zero=True):
        if not self.labels:
            items = [(k, k) for (i, k) in enumerate(self.theset)]
        else:
            items = [(k, self.labels[i]) for (i, k) in enumerate(self.theset)]
        if self.sort:
            items.sort(_options_sorter)
        if zero and self.zero is not None and not self.multiple:
            items.insert(0, ('', self.zero))
        return items

    def __call__(self, value):
        if self.multiple:
            if not value:
                values = []
            elif isinstance(value, (tuple, list)):
                values = value
            else:
                values = [value]
        else:
            values = [value]
        thestrset = [str(x) for x in self.theset]
        failures = [x for x in values if not str(x) in thestrset]
        if failures and self.theset:
            if self.multiple and (value is None or value == ''):
                return ([], None)
            return (value, _translate(self.error_message))
        if self.multiple:
            if isinstance(self.multiple, (tuple, list)) and \
                    not self.multiple[0] <= len(values) < self.multiple[1]:
                return (values, _translate(self.error_message))
            return (values, None)
        return (value, None)


class inDb(Validator):
    """
    Used for reference fields, rendered as a dropbox
    """
    regex1 = re.compile('\w+\.\w+')
    regex2 = re.compile('%\(([^\)]+)\)\d*(?:\.\d+)?[a-zA-Z]')

    def __init__(
        self,
        dbset,
        field,
        label=None,
        error_message='Value not in database',
        orderby=None,
        groupby=None,
        distinct=None,
        cache=None,
        multiple=False,
        zero='',
        sort=False,
        _and=None,
    ):
        from pydal.objects import Table
        if isinstance(field, Table):
            field = field._id

        if hasattr(dbset, 'define_table'):
            self.dbset = dbset()
        else:
            self.dbset = dbset
        (ktable, kfield) = str(field).split('.')
        if not label:
            label = '%%(%s)s' % kfield
        if isinstance(label, str):
            if self.regex1.match(str(label)):
                label = '%%(%s)s' % str(label).split('.')[-1]
            ks = self.regex2.findall(label)
            if kfield not in ks:
                ks += [kfield]
            fields = ks
        else:
            ks = [kfield]
            fields = 'all'
        self.fields = fields
        self.label = label
        self.ktable = ktable
        self.kfield = kfield
        self.ks = ks
        self.error_message = error_message
        self.theset = None
        self.orderby = orderby
        self.groupby = groupby
        self.distinct = distinct
        self.cache = cache
        self.multiple = multiple
        self.zero = zero
        self.sort = sort
        self._and = _and

    def set_self_id(self, id):
        if self._and:
            self._and.record_id = id

    def build_set(self):
        from pydal.objects import FieldVirtual, FieldMethod
        table = self.dbset.db[self.ktable]
        if self.fields == 'all':
            fields = [f for f in table]
        else:
            fields = [table[k] for k in self.fields]
        ignore = (FieldVirtual, FieldMethod)
        fields = filter(lambda f: not isinstance(f, ignore), fields)
        if self.dbset.db._dbname != 'gae':
            orderby = self.orderby or reduce(lambda a, b: a | b, fields)
            groupby = self.groupby
            distinct = self.distinct
            dd = dict(orderby=orderby, groupby=groupby,
                      distinct=distinct, cache=self.cache,
                      cacheable=True)
            records = self.dbset(table).select(*fields, **dd)
        else:
            orderby = self.orderby or \
                reduce(lambda a, b: a | b, (
                    f for f in fields if not f.name == 'id'))
            dd = dict(orderby=orderby, cache=self.cache, cacheable=True)
            records = self.dbset(table).select(table.ALL, **dd)
        self.theset = [str(r[self.kfield]) for r in records]
        if isinstance(self.label, str):
            self.labels = [self.label % r for r in records]
        else:
            self.labels = [self.label(r) for r in records]

    def options(self, zero=True):
        self.build_set()
        items = [(k, self.labels[i]) for (i, k) in enumerate(self.theset)]
        if self.sort:
            items.sort(_options_sorter)
        if zero and self.zero is not None and not self.multiple:
            items.insert(0, ('', self.zero))
        return items

    def __call__(self, value):
        table = self.dbset.db[self.ktable]
        field = table[self.kfield]
        if self.multiple:
            if self._and:
                raise NotImplementedError
            if isinstance(value, list):
                values = value
            elif value:
                values = [value]
            else:
                values = []
            if isinstance(self.multiple, (tuple, list)) and \
                    not self.multiple[0] <= len(values) < self.multiple[1]:
                return (values, _translate(self.error_message))
            if self.theset:
                if not [v for v in values if v not in self.theset]:
                    return (values, None)
            else:
                from pydal.adapters import GoogleDatastoreAdapter

                def count(values, s=self.dbset, f=field):
                    return s(f.belongs(map(int, values))).count()
                if isinstance(self.dbset.db._adapter, GoogleDatastoreAdapter):
                    range_ids = range(0, len(values), 30)
                    total = sum(count(values[i:i + 30]) for i in range_ids)
                    if total == len(values):
                        return (values, None)
                elif count(values) == len(values):
                    return (values, None)
        elif self.theset:
            if str(value) in self.theset:
                if self._and:
                    return self._and(value)
                else:
                    return (value, None)
        else:
            if self.dbset(field == value).count():
                if self._and:
                    return self._and(value)
                else:
                    return (value, None)
        return (value, _translate(self.error_message))


class notInDb(Validator):
    """
    makes the field unique
    """

    def __init__(
        self,
        dbset,
        field,
        error_message='Value already in database or empty',
        allowed_override=[],
        ignore_common_filters=False,
    ):

        from pydal.objects import Table
        if isinstance(field, Table):
            field = field._id

        if hasattr(dbset, 'define_table'):
            self.dbset = dbset()
        else:
            self.dbset = dbset
        self.field = field
        self.error_message = error_message
        self.record_id = 0
        self.allowed_override = allowed_override
        self.ignore_common_filters = ignore_common_filters

    def set_self_id(self, id):
        self.record_id = id

    def __call__(self, value):
        if isinstance(value, unicode):
            value = value.encode('utf8')
        else:
            value = str(value)
        if not value.strip():
            return (value, _translate(self.error_message))
        if value in self.allowed_override:
            return (value, None)
        (tablename, fieldname) = str(self.field).split('.')
        table = self.dbset.db[tablename]
        field = table[fieldname]
        subset = self.dbset(field == value,
                            ignore_common_filters=self.ignore_common_filters)
        id = self.record_id
        if isinstance(id, dict):
            fields = [table[f] for f in id]
            row = subset.select(*fields, **dict(
                limitby=(0, 1), orderby_on_limitby=False)).first()
            if row and any(str(row[f]) != str(id[f]) for f in id):
                return (value, _translate(self.error_message))
        else:
            row = subset.select(table._id, field, limitby=(0, 1),
                                orderby_on_limitby=False).first()
            if row and str(row.id) != str(id):
                return (value, _translate(self.error_message))
        return (value, None)


def _range_error_message(error_message, what_to_enter, minimum, maximum):
    "build the error message for the number range validators"
    if error_message is None:
        error_message = 'Enter ' + what_to_enter
        if minimum is not None and maximum is not None:
            error_message += ' between %(min)g and %(max)g'
        elif minimum is not None:
            error_message += ' greater than or equal to %(min)g'
        elif maximum is not None:
            error_message += ' less than or equal to %(max)g'
    if type(maximum) in [int, long]:
        maximum -= 1
    return _translate(error_message) % dict(min=minimum, max=maximum)


class isIntInRange(Validator):
    """
    Determines that the argument is (or can be represented as) an int,
    and that it falls within the specified range. The range is interpreted
    in the Pythonic way, so the test is: min <= value < max.

    The minimum and maximum limits can be None.
    """
    regex_isint = re.compile('^[+-]?\d+$')

    def __init__(
        self,
        minimum=None,
        maximum=None,
        error_message=None,
    ):
        self.minimum = int(minimum) if minimum is not None else None
        self.maximum = int(maximum) if maximum is not None else None
        self.error_message = _range_error_message(
            error_message, 'an integer', self.minimum, self.maximum)

    def __call__(self, value):
        if self.regex_isint.match(str(value)):
            v = int(value)
            if ((self.minimum is None or v >= self.minimum) and
                    (self.maximum is None or v < self.maximum)):
                return (v, None)
        return (value, self.error_message)


def _str2dec(number):
    s = str(number)
    if '.' not in s:
        s += '.00'
    else:
        s += '0' * (2 - len(s.split('.')[1]))
    return s


class isFloatInRange(Validator):
    """
    Determines that the argument is (or can be represented as) a float,
    and that it falls within the specified inclusive range.
    The comparison is made with native arithmetic.

    The minimum and maximum limits can be None, meaning no lower or upper
    limit, respectively.
    """

    def __init__(
        self,
        minimum=None,
        maximum=None,
        error_message=None,
        dot='.'
    ):
        self.minimum = float(minimum) if minimum is not None else None
        self.maximum = float(maximum) if maximum is not None else None
        self.dot = str(dot)
        self.error_message = _range_error_message(
            error_message, 'a number', self.minimum, self.maximum)

    def __call__(self, value):
        try:
            if self.dot == '.':
                v = float(value)
            else:
                v = float(str(value).replace(self.dot, '.'))
            if ((self.minimum is None or v >= self.minimum) and
                    (self.maximum is None or v <= self.maximum)):
                return (v, None)
        except (ValueError, TypeError):
            pass
        return (value, self.error_message)

    def formatter(self, value):
        if value is None:
            return None
        return _str2dec(value).replace('.', self.dot)


class isDecimalInRange(Validator):
    """
    Determines that the argument is (or can be represented as) a Python
    Decimal, and that it falls within the specified inclusive range.
    The comparison is made with Python Decimal arithmetic.

    The minimum and maximum limits can be None, meaning no lower or upper
    limit, respectively.
    """

    def __init__(
        self,
        minimum=None,
        maximum=None,
        error_message=None,
        dot='.'
    ):
        self.minimum = decimal.Decimal(str(minimum)) if minimum is not None \
            else None
        self.maximum = decimal.Decimal(str(maximum)) if maximum is not None \
            else None
        self.dot = str(dot)
        self.error_message = _range_error_message(
            error_message, 'a number', self.minimum, self.maximum)

    def __call__(self, value):
        try:
            if isinstance(value, decimal.Decimal):
                v = value
            else:
                v = decimal.Decimal(str(value).replace(self.dot, '.'))
            if ((self.minimum is None or v >= self.minimum) and
                    (self.maximum is None or v <= self.maximum)):
                return (v, None)
        except (ValueError, TypeError, decimal.InvalidOperation):
            pass
        return (value, self.error_message)

    def formatter(self, value):
        if value is None:
            return None
        return _str2dec(value).replace('.', self.dot)


def _is_empty(value, empty_regex=None):
    "test empty field"
    if isinstance(value, (str, unicode)):
        value = value.strip()
        if empty_regex is not None and empty_regex.match(value):
            value = ''
    if value is None or value == '' or value == []:
        return (value, True)
    return (value, False)


class isntEmpty(Validator):
    def __init__(self, error_message='Enter a value', empty_regex=None):
        self.error_message = error_message
        if empty_regex is not None:
            self.empty_regex = re.compile(empty_regex)
        else:
            self.empty_regex = None

    def __call__(self, value):
        value, empty = _is_empty(value, empty_regex=self.empty_regex)
        if empty:
            return (value, _translate(self.error_message))
        return (value, None)


class isAlphanumeric(Matches):
    def __init__(self,
                 error_message='Enter only letters, numbers, and underscore'):
        Matches.__init__(self, '^[\w]*$', error_message)


class isEmail(Validator):
    """
    Checks if field's value is a valid email address. Can be set to disallow
    or force addresses from certain domain(s).

    Email regex adapted from
    http://haacked.com/archive/2007/08/21/i-knew-how-to-validate-an-email-address-until-i.aspx,
    generally following the RFCs, except that we disallow quoted strings
    and permit underscores and leading numerics in subdomain labels

    Args:
        banned: regex text for disallowed address domains
        forced: regex text for required address domains

    Both arguments can also be custom objects with a match(value) method.
    """

    regex = re.compile("^(?!\.)([-a-z0-9!\#$%&'*+/=?^_`{|}~]|(?<!\.)\.)+(?<!\.)@(localhost|([a-z0-9]([-\w]*[a-z0-9])?\.)+[a-z]{2,})$", re.VERBOSE | re.IGNORECASE)

    def __init__(self,
                 banned=None,
                 forced=None,
                 error_message='Enter a valid email address'):
        if isinstance(banned, str):
            banned = re.compile(banned)
        if isinstance(forced, str):
            forced = re.compile(forced)
        self.banned = banned
        self.forced = forced
        self.error_message = error_message

    def __call__(self, value):
        match = self.regex.match(value)
        if match:
            domain = value.split('@')[1]
            if (not self.banned or not self.banned.match(domain)) \
                    and (not self.forced or self.forced.match(domain)):
                return (value, None)
        return (value, _translate(self.error_message))


class isEmailList(object):
    split_emails = re.compile('[^,;\s]+')

    def __init__(self, error_message='Invalid emails: %s'):
        self.error_message = error_message

    def __call__(self, value):
        bad_emails = []
        emails = []
        f = isEmail()
        for email in self.split_emails.findall(value):
            if email not in emails:
                emails.append(email)
            error = f(email)[1]
            if error and email not in bad_emails:
                bad_emails.append(email)
        if not bad_emails:
            return (value, None)
        else:
            return (value,
                    _translate(self.error_message) % ', '.join(bad_emails))

    def formatter(self, value, row=None):
        return ', '.join(value or [])


_url_split_regex = \
    re.compile('^(([^:/?#]+):)?(//([^/?#]*))?([^?#]*)(\?([^#]*))?(#(.*))?')


def _escape_unicode(string):
    '''
    Converts a unicode string into US-ASCII, using a simple conversion scheme.
    Each unicode character that does not have a US-ASCII equivalent is
    converted into a URL escaped form based on its hexadecimal value.
    For example, the unicode character '\u4e86' will become the string '%4e%86'

    Args:
        string: unicode string, the unicode string to convert into an
            escaped US-ASCII form

    Returns:
        string: the US-ASCII escaped form of the inputted string

    @author: Jonathan Benn
    '''
    returnValue = StringIO()

    for character in string:
        code = ord(character)
        if code > 0x7F:
            hexCode = hex(code)
            returnValue.write('%' + hexCode[2:4] + '%' + hexCode[4:6])
        else:
            returnValue.write(character)

    return returnValue.getvalue()


def _unicode_to_ascii_authority(authority):
    '''
    Follows the steps in RFC 3490, Section 4 to convert a unicode authority
    string into its ASCII equivalent.
    For example, u'www.Alliancefran\xe7aise.nu' will be converted into
    'www.xn--alliancefranaise-npb.nu'

    Args:
        authority: unicode string, the URL authority component to convert,
            e.g. u'www.Alliancefran\xe7aise.nu'

    Returns:
        string: the US-ASCII character equivalent to the inputed authority,
             e.g. 'www.xn--alliancefranaise-npb.nu'

    Raises:
        Exception: if the function is not able to convert the inputed
            authority

    @author: Jonathan Benn
    '''
    label_split_regex = re.compile(u'[\u002e\u3002\uff0e\uff61]')

    #RFC 3490, Section 4, Step 1
    #The encodings.idna Python module assumes that AllowUnassigned == True

    #RFC 3490, Section 4, Step 2
    labels = label_split_regex.split(authority)

    #RFC 3490, Section 4, Step 3
    #The encodings.idna Python module assumes that UseSTD3ASCIIRules == False

    #RFC 3490, Section 4, Step 4
    #We use the ToASCII operation because we are about to put the authority
    #into an IDN-unaware slot
    asciiLabels = []
    try:
        import encodings.idna
        for label in labels:
            if label:
                asciiLabels.append(encodings.idna.ToASCII(label))
            else:
                #encodings.idna.ToASCII does not accept an empty string, but
                #it is necessary for us to allow for empty labels so that we
                #don't modify the URL
                asciiLabels.append('')
    except:
        asciiLabels = [str(label) for label in labels]
    #RFC 3490, Section 4, Step 5
    return str(reduce(lambda x, y: x + unichr(0x002E) + y, asciiLabels))


def _unicode_to_ascii_url(url, prepend_scheme):
    '''
    Converts the inputed unicode url into a US-ASCII equivalent. This function
    goes a little beyond RFC 3490, which is limited in scope to the domain name
    (authority) only. Here, the functionality is expanded to what was observed
    on Wikipedia on 2009-Jan-22:

       Component    Can Use Unicode?
       ---------    ----------------
       scheme       No
       authority    Yes
       path         Yes
       query        Yes
       fragment     No

    The authority component gets converted to punycode, but occurrences of
    unicode in other components get converted into a pair of URI escapes (we
    assume 4-byte unicode). E.g. the unicode character U+4E2D will be
    converted into '%4E%2D'. Testing with Firefox v3.0.5 has shown that it can
    understand this kind of URI encoding.

    Args:
        url: unicode string, the URL to convert from unicode into US-ASCII
        prepend_scheme: string, a protocol scheme to prepend to the URL if
            we're having trouble parsing it.
            e.g. "http". Input None to disable this functionality

    Returns:
        string: a US-ASCII equivalent of the inputed url

    @author: Jonathan Benn
    '''
    #convert the authority component of the URL into an ASCII punycode string,
    #but encode the rest using the regular URI character encoding

    groups = _url_split_regex.match(url).groups()
    #If no authority was found
    if not groups[3]:
        #Try appending a scheme to see if that fixes the problem
        scheme_to_prepend = prepend_scheme or 'http'
        groups = _url_split_regex.match(
            unicode(scheme_to_prepend) + u'://' + url).groups()
    #if we still can't find the authority
    if not groups[3]:
        raise Exception('No authority component found, ' +
                        'could not decode unicode to US-ASCII')

    #We're here if we found an authority, let's rebuild the URL
    scheme = groups[1]
    authority = groups[3]
    path = groups[4] or ''
    query = groups[5] or ''
    fragment = groups[7] or ''

    if prepend_scheme:
        scheme = str(scheme) + '://'
    else:
        scheme = ''
    return scheme + _unicode_to_ascii_authority(authority) +\
        _escape_unicode(path) + _escape_unicode(query) + str(fragment)


class _isGenericUrl(Validator):
    """
    Rejects a URL string if any of the following is true:
       * The string is empty or None
       * The string uses characters that are not allowed in a URL
       * The URL scheme specified (if one is specified) is not valid

    Based on RFC 2396: http://www.faqs.org/rfcs/rfc2396.html

    This function only checks the URL's syntax. It does not check that the URL
    points to a real document, for example, or that it otherwise makes sense
    semantically. This function does automatically prepend 'http://' in front
    of a URL if and only if that's necessary to successfully parse the URL.
    Please note that a scheme will be prepended only for rare cases
    (e.g. 'google.ca:80')

    The list of allowed schemes is customizable with the allowed_schemes
    parameter. If you exclude None from the list, then abbreviated URLs
    (lacking a scheme such as 'http') will be rejected.

    The default prepended scheme is customizable with the prepend_scheme
    parameter. If you set prepend_scheme to None then prepending will be
    disabled. URLs that require prepending to parse will still be accepted,
    but the return value will not be modified.

    @author: Jonathan Benn

    Args:
        error_message: a string, the error message to give the end user
            if the URL does not validate
        allowed_schemes: a list containing strings or None. Each element
            is a scheme the inputed URL is allowed to use
        prepend_scheme: a string, this scheme is prepended if it's
            necessary to make the URL valid

    """
    official_url_schemes = [
        'aaa', 'aaas', 'acap', 'cap', 'cid', 'crid', 'data', 'dav', 'dict',
        'dns', 'fax', 'file', 'ftp', 'go', 'gopher', 'h323', 'http', 'https',
        'icap', 'im', 'imap', 'info', 'ipp', 'iris', 'iris.beep', 'iris.xpc',
        'iris.xpcs', 'iris.lws', 'ldap', 'mailto', 'mid', 'modem', 'msrp',
        'msrps', 'mtqp', 'mupdate', 'news', 'nfs', 'nntp', 'opaquelocktoken',
        'pop', 'pres', 'prospero', 'rtsp', 'service', 'shttp', 'sip', 'sips',
        'snmp', 'soap.beep', 'soap.beeps', 'tag', 'tel', 'telnet', 'tftp',
        'thismessage', 'tip', 'tv', 'urn', 'vemmi', 'wais', 'xmlrpc.beep',
        'xmlrpc.beep', 'xmpp', 'z39.50r', 'z39.50s'
    ]
    unofficial_url_schemes = [
        'about', 'adiumxtra', 'aim', 'afp', 'aw', 'callto', 'chrome', 'cvs',
        'ed2k', 'feed', 'fish', 'gg', 'gizmoproject', 'iax2', 'irc', 'ircs',
        'itms', 'jar', 'javascript', 'keyparc', 'lastfm', 'ldaps', 'magnet',
        'mms', 'msnim', 'mvn', 'notes', 'nsfw', 'psyc', 'paparazzi:http',
        'rmi', 'rsync', 'secondlife', 'sgn', 'skype', 'ssh', 'sftp', 'smb',
        'sms', 'soldat', 'steam', 'svn', 'teamspeak', 'unreal', 'ut2004',
        'ventrilo', 'view-source', 'webcal', 'wyciwyg', 'xfire', 'xri', 'ymsgr'
    ]
    all_url_schemes = [None] + official_url_schemes + unofficial_url_schemes

    def __init__(
        self,
        error_message='Enter a valid URL',
        allowed_schemes=None,
        prepend_scheme=None,
    ):

        self.error_message = error_message
        if allowed_schemes is None:
            self.allowed_schemes = self.all_url_schemes
        else:
            self.allowed_schemes = allowed_schemes
        self.prepend_scheme = prepend_scheme
        if self.prepend_scheme not in self.allowed_schemes:
            raise SyntaxError(
                "prepend_scheme='%s' is not in allowed_schemes=%s" %
                (self.prepend_scheme, self.allowed_schemes))

    GENERIC_URL = re.compile(r"%[^0-9A-Fa-f]{2}|%[^0-9A-Fa-f][0-9A-Fa-f]|%[0-9A-Fa-f][^0-9A-Fa-f]|%$|%[0-9A-Fa-f]$|%[^0-9A-Fa-f]$")
    GENERIC_URL_VALID = re.compile(r"[A-Za-z0-9;/?:@&=+$,\-_\.!~*'\(\)%#]+$")

    def __call__(self, value):
        """
        Args:
            value: a string, the URL to validate

        Returns:
            a tuple, where tuple[0] is the inputed value (possible
            prepended with prepend_scheme), and tuple[1] is either
            None (success!) or the string error_message
        """
        try:
            # if the URL does not misuse the '%' character
            if not self.GENERIC_URL.search(value):
                # if the URL is only composed of valid characters
                if self.GENERIC_URL_VALID.match(value):
                    # Then split up the URL into its components and check on
                    # the scheme
                    scheme = _url_split_regex.match(value).group(2)
                    # Clean up the scheme before we check it
                    if scheme is not None:
                        scheme = urllib.unquote(scheme).lower()
                    # If the scheme really exists
                    if scheme in self.allowed_schemes:
                        # Then the URL is valid
                        return (value, None)
                    else:
                        # else, for the possible case of abbreviated URLs with
                        # ports, check to see if adding a valid scheme fixes
                        # the problem (but only do this if it doesn't have
                        # one already!)
                        if value.find('://') < 0 and \
                                None in self.allowed_schemes:
                            schemeToUse = self.prepend_scheme or 'http'
                            prependTest = self.__call__(
                                schemeToUse + '://' + value)
                            # if the prepend test succeeded
                            if prependTest[1] is None:
                                # if prepending in the output is enabled
                                if self.prepend_scheme:
                                    return prependTest
                                else:
                                    # else return the original,
                                    #  non-prepended value
                                    return (value, None)
        except:
            pass
        # else the URL is not valid
        return (value, _translate(self.error_message))


class _isHTTPUrl(Validator):
    """
    Rejects a URL string if any of the following is true:
       * The string is empty or None
       * The string uses characters that are not allowed in a URL
       * The string breaks any of the HTTP syntactic rules
       * The URL scheme specified (if one is specified) is not 'http' or
         'https'
       * The top-level domain (if a host name is specified) does not exist

    Based on RFC 2616: http://www.faqs.org/rfcs/rfc2616.html

    This function only checks the URL's syntax. It does not check that the URL
    points to a real document, for example, or that it otherwise makes sense
    semantically. This function does automatically prepend 'http://' in front
    of a URL in the case of an abbreviated URL (e.g. 'google.ca').

    The list of allowed schemes is customizable with the allowed_schemes
    parameter. If you exclude None from the list, then abbreviated URLs
    (lacking a scheme such as 'http') will be rejected.

    The default prepended scheme is customizable with the prepend_scheme
    parameter. If you set prepend_scheme to None then prepending will be
    disabled. URLs that require prepending to parse will still be accepted,
    but the return value will not be modified.

    @author: Jonathan Benn

    Args:
        error_message: a string, the error message to give the end user
            if the URL does not validate
        allowed_schemes: a list containing strings or None. Each element
            is a scheme the inputed URL is allowed to use
        prepend_scheme: a string, this scheme is prepended if it's
            necessary to make the URL valid
    """

    official_top_level_domains = [
        # a
        'abogado', 'ac', 'academy', 'accountants', 'active', 'actor',
        'ad', 'adult', 'ae', 'aero', 'af', 'ag', 'agency', 'ai',
        'airforce', 'al', 'allfinanz', 'alsace', 'am', 'amsterdam', 'an',
        'android', 'ao', 'apartments', 'aq', 'aquarelle', 'ar', 'archi',
        'army', 'arpa', 'as', 'asia', 'associates', 'at', 'attorney',
        'au', 'auction', 'audio', 'autos', 'aw', 'ax', 'axa', 'az',
        # b
        'ba', 'band', 'bank', 'bar', 'barclaycard', 'barclays',
        'bargains', 'bayern', 'bb', 'bd', 'be', 'beer', 'berlin', 'best',
        'bf', 'bg', 'bh', 'bi', 'bid', 'bike', 'bingo', 'bio', 'biz',
        'bj', 'black', 'blackfriday', 'bloomberg', 'blue', 'bm', 'bmw',
        'bn', 'bnpparibas', 'bo', 'boo', 'boutique', 'br', 'brussels',
        'bs', 'bt', 'budapest', 'build', 'builders', 'business', 'buzz',
        'bv', 'bw', 'by', 'bz', 'bzh',
        # c
        'ca', 'cab', 'cal', 'camera', 'camp', 'cancerresearch', 'canon',
        'capetown', 'capital', 'caravan', 'cards', 'care', 'career',
        'careers', 'cartier', 'casa', 'cash', 'casino', 'cat',
        'catering', 'cbn', 'cc', 'cd', 'center', 'ceo', 'cern', 'cf',
        'cg', 'ch', 'channel', 'chat', 'cheap', 'christmas', 'chrome',
        'church', 'ci', 'citic', 'city', 'ck', 'cl', 'claims',
        'cleaning', 'click', 'clinic', 'clothing', 'club', 'cm', 'cn',
        'co', 'coach', 'codes', 'coffee', 'college', 'cologne', 'com',
        'community', 'company', 'computer', 'condos', 'construction',
        'consulting', 'contractors', 'cooking', 'cool', 'coop',
        'country', 'cr', 'credit', 'creditcard', 'cricket', 'crs',
        'cruises', 'cu', 'cuisinella', 'cv', 'cw', 'cx', 'cy', 'cymru',
        'cz',
        # d
        'dabur', 'dad', 'dance', 'dating', 'day', 'dclk', 'de', 'deals',
        'degree', 'delivery', 'democrat', 'dental', 'dentist', 'desi',
        'design', 'dev', 'diamonds', 'diet', 'digital', 'direct',
        'directory', 'discount', 'dj', 'dk', 'dm', 'dnp', 'do', 'docs',
        'domains', 'doosan', 'durban', 'dvag', 'dz',
        # e
        'eat', 'ec', 'edu', 'education', 'ee', 'eg', 'email', 'emerck',
        'energy', 'engineer', 'engineering', 'enterprises', 'equipment',
        'er', 'es', 'esq', 'estate', 'et', 'eu', 'eurovision', 'eus',
        'events', 'everbank', 'exchange', 'expert', 'exposed',
        # f
        'fail', 'fans', 'farm', 'fashion', 'feedback', 'fi', 'finance',
        'financial', 'firmdale', 'fish', 'fishing', 'fit', 'fitness',
        'fj', 'fk', 'flights', 'florist', 'flowers', 'flsmidth', 'fly',
        'fm', 'fo', 'foo', 'football', 'forsale', 'foundation', 'fr',
        'frl', 'frogans', 'fund', 'furniture', 'futbol',
        # g
        'ga', 'gal', 'gallery', 'garden', 'gb', 'gbiz', 'gd', 'gdn',
        'ge', 'gent', 'gf', 'gg', 'ggee', 'gh', 'gi', 'gift', 'gifts',
        'gives', 'gl', 'glass', 'gle', 'global', 'globo', 'gm', 'gmail',
        'gmo', 'gmx', 'gn', 'goldpoint', 'goog', 'google', 'gop', 'gov',
        'gp', 'gq', 'gr', 'graphics', 'gratis', 'green', 'gripe', 'gs',
        'gt', 'gu', 'guide', 'guitars', 'guru', 'gw', 'gy',
        # h
        'hamburg', 'hangout', 'haus', 'healthcare', 'help', 'here',
        'hermes', 'hiphop', 'hiv', 'hk', 'hm', 'hn', 'holdings',
        'holiday', 'homes', 'horse', 'host', 'hosting', 'house', 'how',
        'hr', 'ht', 'hu',
        # i
        'ibm', 'id', 'ie', 'ifm', 'il', 'im', 'immo', 'immobilien', 'in',
        'industries', 'info', 'ing', 'ink', 'institute', 'insure', 'int',
        'international', 'investments', 'io', 'iq', 'ir', 'irish', 'is',
        'it', 'iwc',
        # j
        'jcb', 'je', 'jetzt', 'jm', 'jo', 'jobs', 'joburg', 'jp',
        'juegos',
        # k
        'kaufen', 'kddi', 'ke', 'kg', 'kh', 'ki', 'kim', 'kitchen',
        'kiwi', 'km', 'kn', 'koeln', 'kp', 'kr', 'krd', 'kred', 'kw',
        'ky', 'kyoto', 'kz',
        # l
        'la', 'lacaixa', 'land', 'lat', 'latrobe', 'lawyer', 'lb', 'lc',
        'lds', 'lease', 'legal', 'lgbt', 'li', 'lidl', 'life',
        'lighting', 'limited', 'limo', 'link', 'lk', 'loans',
        'localhost', 'london', 'lotte', 'lotto', 'lr', 'ls', 'lt',
        'ltda', 'lu', 'luxe', 'luxury', 'lv', 'ly',
        # m
        'ma', 'madrid', 'maison', 'management', 'mango', 'market',
        'marketing', 'marriott', 'mc', 'md', 'me', 'media', 'meet',
        'melbourne', 'meme', 'memorial', 'menu', 'mg', 'mh', 'miami',
        'mil', 'mini', 'mk', 'ml', 'mm', 'mn', 'mo', 'mobi', 'moda',
        'moe', 'monash', 'money', 'mormon', 'mortgage', 'moscow',
        'motorcycles', 'mov', 'mp', 'mq', 'mr', 'ms', 'mt', 'mu',
        'museum', 'mv', 'mw', 'mx', 'my', 'mz',
        # n
        'na', 'nagoya', 'name', 'navy', 'nc', 'ne', 'net', 'network',
        'neustar', 'new', 'nexus', 'nf', 'ng', 'ngo', 'nhk', 'ni',
        'nico', 'ninja', 'nl', 'no', 'np', 'nr', 'nra', 'nrw', 'ntt',
        'nu', 'nyc', 'nz',
        # o
        'okinawa', 'om', 'one', 'ong', 'onl', 'ooo', 'org', 'organic',
        'osaka', 'otsuka', 'ovh',
        # p
        'pa', 'paris', 'partners', 'parts', 'party', 'pe', 'pf', 'pg',
        'ph', 'pharmacy', 'photo', 'photography', 'photos', 'physio',
        'pics', 'pictures', 'pink', 'pizza', 'pk', 'pl', 'place',
        'plumbing', 'pm', 'pn', 'pohl', 'poker', 'porn', 'post', 'pr',
        'praxi', 'press', 'pro', 'prod', 'productions', 'prof',
        'properties', 'property', 'ps', 'pt', 'pub', 'pw', 'py',
        # q
        'qa', 'qpon', 'quebec',
        # r
        're', 'realtor', 'recipes', 'red', 'rehab', 'reise', 'reisen',
        'reit', 'ren', 'rentals', 'repair', 'report', 'republican',
        'rest', 'restaurant', 'reviews', 'rich', 'rio', 'rip', 'ro',
        'rocks', 'rodeo', 'rs', 'rsvp', 'ru', 'ruhr', 'rw', 'ryukyu',
        # s
        'sa', 'saarland', 'sale', 'samsung', 'sarl', 'saxo', 'sb', 'sc',
        'sca', 'scb', 'schmidt', 'school', 'schule', 'schwarz',
        'science', 'scot', 'sd', 'se', 'services', 'sew', 'sexy', 'sg',
        'sh', 'shiksha', 'shoes', 'shriram', 'si', 'singles', 'sj', 'sk',
        'sky', 'sl', 'sm', 'sn', 'so', 'social', 'software', 'sohu',
        'solar', 'solutions', 'soy', 'space', 'spiegel', 'sr', 'st',
        'style', 'su', 'supplies', 'supply', 'support', 'surf',
        'surgery', 'suzuki', 'sv', 'sx', 'sy', 'sydney', 'systems', 'sz',
        # t
        'taipei', 'tatar', 'tattoo', 'tax', 'tc', 'td', 'technology',
        'tel', 'temasek', 'tennis', 'tf', 'tg', 'th', 'tienda', 'tips',
        'tires', 'tirol', 'tj', 'tk', 'tl', 'tm', 'tn', 'to', 'today',
        'tokyo', 'tools', 'top', 'toshiba', 'town', 'toys', 'tp', 'tr',
        'trade', 'training', 'travel', 'trust', 'tt', 'tui', 'tv', 'tw',
        'tz',
        # u
        'ua', 'ug', 'uk', 'university', 'uno', 'uol', 'us', 'uy', 'uz',
        # v
        'va', 'vacations', 'vc', 've', 'vegas', 'ventures',
        'versicherung', 'vet', 'vg', 'vi', 'viajes', 'video', 'villas',
        'vision', 'vlaanderen', 'vn', 'vodka', 'vote', 'voting', 'voto',
        'voyage', 'vu',
        # w
        'wales', 'wang', 'watch', 'webcam', 'website', 'wed', 'wedding',
        'wf', 'whoswho', 'wien', 'wiki', 'williamhill', 'wme', 'work',
        'works', 'world', 'ws', 'wtc', 'wtf',
        # x
        'xn--1qqw23a', 'xn--3bst00m', 'xn--3ds443g', 'xn--3e0b707e',
        'xn--45brj9c', 'xn--45q11c', 'xn--4gbrim', 'xn--55qw42g',
        'xn--55qx5d', 'xn--6frz82g', 'xn--6qq986b3xl', 'xn--80adxhks',
        'xn--80ao21a', 'xn--80asehdb', 'xn--80aswg', 'xn--90a3ac',
        'xn--90ais', 'xn--b4w605ferd', 'xn--c1avg', 'xn--cg4bki',
        'xn--clchc0ea0b2g2a9gcd', 'xn--czr694b', 'xn--czrs0t',
        'xn--czru2d', 'xn--d1acj3b', 'xn--d1alf', 'xn--fiq228c5hs',
        'xn--fiq64b', 'xn--fiqs8s', 'xn--fiqz9s', 'xn--flw351e',
        'xn--fpcrj9c3d', 'xn--fzc2c9e2c', 'xn--gecrj9c', 'xn--h2brj9c',
        'xn--hxt814e', 'xn--i1b6b1a6a2e', 'xn--io0a7i', 'xn--j1amh',
        'xn--j6w193g', 'xn--kprw13d', 'xn--kpry57d', 'xn--kput3i',
        'xn--l1acc', 'xn--lgbbat1ad8j', 'xn--mgb9awbf',
        'xn--mgba3a4f16a', 'xn--mgbaam7a8h', 'xn--mgbab2bd',
        'xn--mgbayh7gpa', 'xn--mgbbh1a71e', 'xn--mgbc0a9azcg',
        'xn--mgberp4a5d4ar', 'xn--mgbx4cd0ab', 'xn--ngbc5azd',
        'xn--node', 'xn--nqv7f', 'xn--nqv7fs00ema', 'xn--o3cw4h',
        'xn--ogbpf8fl', 'xn--p1acf', 'xn--p1ai', 'xn--pgbs0dh',
        'xn--q9jyb4c', 'xn--qcka1pmc', 'xn--rhqv96g', 'xn--s9brj9c',
        'xn--ses554g', 'xn--unup4y', 'xn--vermgensberater-ctb',
        'xn--vermgensberatung-pwb', 'xn--vhquv', 'xn--wgbh1c',
        'xn--wgbl6a', 'xn--xhq521b', 'xn--xkc2al3hye2a',
        'xn--xkc2dl3a5ee0h', 'xn--yfro4i67o', 'xn--ygbi2ammx',
        'xn--zfr164b', 'xxx', 'xyz',
        # y
        'yachts', 'yandex', 'ye', 'yodobashi', 'yoga', 'yokohama',
        'youtube', 'yt',
        # z
        'za', 'zip', 'zm', 'zone', 'zuerich', 'zw'
    ]
    http_schemes = [None, 'http', 'https']
    GENERIC_VALID_IP = re.compile(
        "([\w.!~*'|;:&=+$,-]+@)?\d+\.\d+\.\d+\.\d+(:\d*)*$")
    GENERIC_VALID_DOMAIN = re.compile("([\w.!~*'|;:&=+$,-]+@)?(([A-Za-z0-9]+[A-Za-z0-9\-]*[A-Za-z0-9]+\.)*([A-Za-z0-9]+\.)*)*([A-Za-z]+[A-Za-z0-9\-]*[A-Za-z0-9]+)\.?(:\d*)*$")

    def __init__(self, error_message='Enter a valid URL', allowed_schemes=None,
                 prepend_scheme='http', allowed_tlds=None):
        self.error_message = error_message
        if allowed_schemes is None:
            self.allowed_schemes = self.http_schemes
        else:
            self.allowed_schemes = allowed_schemes
        if allowed_tlds is None:
            self.allowed_tlds = self.official_top_level_domains
        else:
            self.allowed_tlds = allowed_tlds
        self.prepend_scheme = prepend_scheme

        for i in self.allowed_schemes:
            if i not in self.http_schemes:
                raise SyntaxError("allowed_scheme value '%s' is not in %s" %
                                  (i, self.http_schemes))

        if self.prepend_scheme not in self.allowed_schemes:
            raise SyntaxError(
                "prepend_scheme='%s' is not in allowed_schemes=%s" %
                (self.prepend_scheme, self.allowed_schemes))

    def __call__(self, value):
        """
        Args:
            value: a string, the URL to validate

        Returns:
            a tuple, where tuple[0] is the inputed value
            (possible prepended with prepend_scheme), and tuple[1] is either
            None (success!) or the string error_message
        """

        try:
            # if the URL passes generic validation
            x = _isGenericUrl(error_message=self.error_message,
                              allowed_schemes=self.allowed_schemes,
                              prepend_scheme=self.prepend_scheme)
            if x(value)[1] is None:
                componentsMatch = _url_split_regex.match(value)
                authority = componentsMatch.group(4)
                # if there is an authority component
                if authority:
                    # if authority is a valid IP address
                    if self.GENERIC_VALID_IP.match(authority):
                        # Then this HTTP URL is valid
                        return (value, None)
                    else:
                        # else if authority is a valid domain name
                        domainMatch = self.GENERIC_VALID_DOMAIN.match(
                            authority)
                        if domainMatch:
                            # if the top-level domain really exists
                            if domainMatch.group(5).lower()\
                                    in self.allowed_tlds:
                                # Then this HTTP URL is valid
                                return (value, None)
                else:
                    # else this is a relative/abbreviated URL, which will parse
                    # into the URL's path component
                    path = componentsMatch.group(5)
                    # relative case: if this is a valid path (if it starts with
                    # a slash)
                    if path.startswith('/'):
                        # Then this HTTP URL is valid
                        return (value, None)
                    else:
                        # abbreviated case: if we haven't already, prepend a
                        # scheme and see if it fixes the problem
                        if value.find('://') < 0:
                            schemeToUse = self.prepend_scheme or 'http'
                            prependTest = self.__call__(schemeToUse
                                                        + '://' + value)
                            # if the prepend test succeeded
                            if prependTest[1] is None:
                                # if prepending in the output is enabled
                                if self.prepend_scheme:
                                    return prependTest
                                else:
                                    # else return the original, non-prepended
                                    # value
                                    return (value, None)
        except:
            pass
        # else the HTTP URL is not valid
        return (value, _translate(self.error_message))


class isUrl(Validator):
    """
    Rejects a URL string if any of the following is true:

       * The string is empty or None
       * The string uses characters that are not allowed in a URL
       * The string breaks any of the HTTP syntactic rules
       * The URL scheme specified (if one is specified) is not 'http' or
         'https'
       * The top-level domain (if a host name is specified) does not exist

    (These rules are based on RFC 2616: http://www.faqs.org/rfcs/rfc2616.html)

    This function only checks the URL's syntax. It does not check that the URL
    points to a real document, for example, or that it otherwise makes sense
    semantically. This function does automatically prepend 'http://' in front
    of a URL in the case of an abbreviated URL (e.g. 'google.ca').

    If the parameter mode='generic' is used, then this function's behavior
    changes. It then rejects a URL string if any of the following is true:

       * The string is empty or None
       * The string uses characters that are not allowed in a URL
       * The URL scheme specified (if one is specified) is not valid

    (These rules are based on RFC 2396: http://www.faqs.org/rfcs/rfc2396.html)

    The list of allowed schemes is customizable with the allowed_schemes
    parameter. If you exclude None from the list, then abbreviated URLs
    (lacking a scheme such as 'http') will be rejected.

    The default prepended scheme is customizable with the prepend_scheme
    parameter. If you set prepend_scheme to None then prepending will be
    disabled. URLs that require prepending to parse will still be accepted,
    but the return value will not be modified.

    isUrl is compatible with the Internationalized Domain Name (IDN) standard
    specified in RFC 3490 (http://tools.ietf.org/html/rfc3490). As a result,
    URLs can be regular strings or unicode strings.
    If the URL's domain component (e.g. google.ca) contains non-US-ASCII
    letters, then the domain will be converted into Punycode (defined in
    RFC 3492, http://tools.ietf.org/html/rfc3492). isUrl goes a bit beyond
    the standards, and allows non-US-ASCII characters to be present in the path
    and query components of the URL as well. These non-US-ASCII characters will
    be escaped using the standard '%20' type syntax. e.g. the unicode
    character with hex code 0x4e86 will become '%4e%86'

    Args:
        error_message: a string, the error message to give the end user
            if the URL does not validate
        allowed_schemes: a list containing strings or None. Each element
            is a scheme the inputed URL is allowed to use
        prepend_scheme: a string, this scheme is prepended if it's
            necessary to make the URL valid

    @author: Jonathan Benn
    """

    def __init__(self, error_message='Enter a valid URL', mode='http',
                 allowed_schemes=None, prepend_scheme='http',
                 allowed_tlds=None):
        self.error_message = error_message
        self.mode = mode.lower()
        if self.mode not in ['generic', 'http']:
            raise SyntaxError("invalid mode '%s' in isUrl" % self.mode)
        self.allowed_tlds = allowed_tlds
        self.allowed_schemes = allowed_schemes

        if self.allowed_schemes:
            if prepend_scheme not in self.allowed_schemes:
                raise SyntaxError(
                    "prepend_scheme='%s' is not in allowed_schemes=%s"
                    % (prepend_scheme, self.allowed_schemes))

        # if allowed_schemes is None, then we will defer testing
        # prepend_scheme's validity to a sub-method

        self.prepend_scheme = prepend_scheme

    def __call__(self, value):
        """
        Args:
            value: a unicode or regular string, the URL to validate

        Returns:
            a (string, string) tuple, where tuple[0] is the modified
            input value and tuple[1] is either None (success!) or the
            string error_message. The input value will never be modified in the
            case of an error. However, if there is success then the input URL
            may be modified to (1) prepend a scheme, and/or (2) convert a
            non-compliant unicode URL into a compliant US-ASCII version.
        """

        if self.mode == 'generic':
            subMethod = _isGenericUrl(error_message=self.error_message,
                                      allowed_schemes=self.allowed_schemes,
                                      prepend_scheme=self.prepend_scheme)
        elif self.mode == 'http':
            subMethod = _isHTTPUrl(error_message=self.error_message,
                                   allowed_schemes=self.allowed_schemes,
                                   prepend_scheme=self.prepend_scheme,
                                   allowed_tlds=self.allowed_tlds)
        else:
            raise SyntaxError("invalid mode '%s' in isUrl" % self.mode)

        if type(value) != unicode:
            return subMethod(value)
        else:
            try:
                asciiValue = _unicode_to_ascii_url(value, self.prepend_scheme)
            except Exception:
                #If we are not able to convert the unicode url into a
                # US-ASCII URL, then the URL is not valid
                return (value, _translate(self.error_message))

            methodResult = subMethod(asciiValue)
            #if the validation of the US-ASCII version of the value failed
            if not methodResult[1] is None:
                # then return the original input value, not the US-ASCII
                return (value, methodResult[1])
            else:
                return methodResult


_regex_time = re.compile('((?P<h>[0-9]+))([^0-9 ]+(?P<m>[0-9 ]+))?([^0-9ap ]+(?P<s>[0-9]*))?((?P<d>[ap]m))?')


class isTime(Validator):
    """
    understands the following formats
    hh:mm:ss [am/pm]
    hh:mm [am/pm]
    hh [am/pm]

    [am/pm] is optional, ':' can be replaced by any other non-space non-digit::
    """

    def __init__(self, error_message='Enter time as hh:mm:ss (seconds, am, pm optional)'):
        self.error_message = error_message

    def __call__(self, value):
        try:
            ivalue = value
            value = _regex_time.match(value.lower())
            (h, m, s) = (int(value.group('h')), 0, 0)
            if not value.group('m') is None:
                m = int(value.group('m'))
            if not value.group('s') is None:
                s = int(value.group('s'))
            if value.group('d') == 'pm' and 0 < h < 12:
                h = h + 12
            if value.group('d') == 'am' and h == 12:
                h = 0
            if not (h in range(24) and m in range(60) and s
                    in range(60)):
                raise ValueError(
                    'Hours or minutes or seconds are outside of allowed range')
            value = datetime.time(h, m, s)
            return (value, None)
        except AttributeError:
            pass
        except ValueError:
            pass
        return (ivalue, _translate(self.error_message))


class _UTC(datetime.tzinfo):
    """UTC"""
    ZERO = datetime.timedelta(0)

    def utcoffset(self, dt):
        return _UTC.ZERO

    def tzname(self, dt):
        return "UTC"

    def dst(self, dt):
        return _UTC.ZERO

_utc = _UTC()


class isDate(Validator):
    """
    date has to be in the ISO8960 format YYYY-MM-DD
    timezome must be None or a pytz.timezone("America/Chicago") object
    """

    def __init__(self, format='%Y-%m-%d',
                 error_message='Enter date as %(format)s',
                 timezone=None):
        self.format = _translate(format)
        self.error_message = str(error_message)
        self.timezone = timezone
        self.extremes = {}

    def __call__(self, value):
        ovalue = value
        if isinstance(value, datetime.date):
            if self.timezone is not None:
                value = value - datetime.timedelta(seconds=self.timezone*3600)
            return (value, None)
        try:
            (y, m, d, hh, mm, ss, t0, t1, t2) = \
                time.strptime(value, str(self.format))
            value = datetime.date(y, m, d)
            if self.timezone is not None:
                value = self.timezone.localize(value).astimezone(_utc)
            return (value, None)
        except:
            self.extremes.update(isDatetime.nice(self.format))
            return (ovalue, _translate(self.error_message) % self.extremes)

    def formatter(self, value):
        if value is None:
            return None
        format = self.format
        year = value.year
        y = '%.4i' % year
        format = format.replace('%y', y[-2:])
        format = format.replace('%Y', y)
        if year < 1900:
            year = 2000
        if self.timezone is not None:
            d = datetime.datetime(year, value.month, value.day)
            d = d.replace(tzinfo=_utc).astimezone(self.timezone)
        else:
            d = datetime.date(year, value.month, value.day)
        return d.strftime(format)


class isDatetime(Validator):
    """
    datetime has to be in the ISO8960 format YYYY-MM-DD hh:mm:ss
    timezome must be None or a pytz.timezone("America/Chicago") object
    """

    isodatetime = '%Y-%m-%d %H:%M:%S'

    @staticmethod
    def nice(format):
        code = (('%Y', '1963'),
                ('%y', '63'),
                ('%d', '28'),
                ('%m', '08'),
                ('%b', 'Aug'),
                ('%B', 'August'),
                ('%H', '14'),
                ('%I', '02'),
                ('%p', 'PM'),
                ('%M', '30'),
                ('%S', '59'))
        for (a, b) in code:
            format = format.replace(a, b)
        return dict(format=format)

    def __init__(self, format='%Y-%m-%d %H:%M:%S',
                 error_message='Enter date and time as %(format)s',
                 timezone=None):
        self.format = _translate(format)
        self.error_message = str(error_message)
        self.extremes = {}
        self.timezone = timezone

    def __call__(self, value):
        ovalue = value
        if isinstance(value, datetime.datetime):
            return (value, None)
        try:
            (y, m, d, hh, mm, ss, t0, t1, t2) = \
                time.strptime(value, str(self.format))
            value = datetime.datetime(y, m, d, hh, mm, ss)
            if self.timezone is not None:
                value = self.timezone.localize(value).astimezone(_utc)
            return (value, None)
        except:
            self.extremes.update(isDatetime.nice(self.format))
            return (ovalue, _translate(self.error_message) % self.extremes)

    def formatter(self, value):
        if value is None:
            return None
        format = self.format
        year = value.year
        y = '%.4i' % year
        format = format.replace('%y', y[-2:])
        format = format.replace('%Y', y)
        if year < 1900:
            year = 2000
        d = datetime.datetime(year, value.month, value.day,
                              value.hour, value.minute, value.second)
        if self.timezone is not None:
            d = d.replace(tzinfo=_utc).astimezone(self.timezone)
        return d.strftime(format)


class isDateInRange(isDate):
    def __init__(self,
                 minimum=None,
                 maximum=None,
                 format='%Y-%m-%d',
                 error_message=None,
                 timezone=None):
        self.minimum = minimum
        self.maximum = maximum
        if error_message is None:
            if minimum is None:
                error_message = "Enter date on or before %(max)s"
            elif maximum is None:
                error_message = "Enter date on or after %(min)s"
            else:
                error_message = "Enter date in range %(min)s %(max)s"
        isDate.__init__(self, format=format, error_message=error_message,
                        timezone=timezone)
        self.extremes = dict(min=self.formatter(minimum),
                             max=self.formatter(maximum))

    def __call__(self, value):
        ovalue = value
        (value, msg) = isDate.__call__(self, value)
        if msg is not None:
            return (value, msg)
        if self.minimum and self.minimum > value:
            return (ovalue, _translate(self.error_message) % self.extremes)
        if self.maximum and value > self.maximum:
            return (ovalue, _translate(self.error_message) % self.extremes)
        return (value, None)


class isDatetimeInRange(isDatetime):
    def __init__(self,
                 minimum=None,
                 maximum=None,
                 format='%Y-%m-%d %H:%M:%S',
                 error_message=None,
                 timezone=None):
        self.minimum = minimum
        self.maximum = maximum
        if error_message is None:
            if minimum is None:
                error_message = "Enter date and time on or before %(max)s"
            elif maximum is None:
                error_message = "Enter date and time on or after %(min)s"
            else:
                error_message = "Enter date and time in range %(min)s %(max)s"
        isDatetime.__init__(self, format=format, error_message=error_message,
                            timezone=timezone)
        self.extremes = dict(min=self.formatter(minimum),
                             max=self.formatter(maximum))

    def __call__(self, value):
        ovalue = value
        (value, msg) = isDatetime.__call__(self, value)
        if msg is not None:
            return (value, msg)
        if self.minimum and self.minimum > value:
            return (ovalue, _translate(self.error_message) % self.extremes)
        if self.maximum and value > self.maximum:
            return (ovalue, _translate(self.error_message) % self.extremes)
        return (value, None)


class isListOf(Validator):
    def __init__(self, other=None, minimum=0, maximum=100,
                 error_message=None):
        self.other = other
        self.minimum = minimum
        self.maximum = maximum
        self.error_message = error_message or \
            "Enter between %(min)g and %(max)g values"

    def __call__(self, value):
        ivalue = value
        if not isinstance(value, list):
            ivalue = [ivalue]
        ivalue = [i for i in ivalue if str(i).strip()]
        if self.minimum is not None and len(ivalue) < self.minimum:
            return (ivalue, _translate(self.error_message) % dict(
                min=self.minimum, max=self.maximum))
        if self.maximum is not None and len(ivalue) > self.maximum:
            return (ivalue, _translate(self.error_message) % dict(
                min=self.minimum, max=self.maximum))
        new_value = []
        other = self.other
        if self.other:
            if not isinstance(other, (list, tuple)):
                other = [other]
            for item in ivalue:
                v = item
                for validator in other:
                    (v, e) = validator(v)
                    if e:
                        return (ivalue, e)
                new_value.append(v)
            ivalue = new_value
        return (ivalue, None)


class Lower(Validator):
    """
    Converts to lower case
    """

    def __call__(self, value):
        return (value.decode('utf8').lower().encode('utf8'), None)


class Upper(Validator):
    """
    Converts to upper case::
    """

    def __call__(self, value):
        return (value.decode('utf8').upper().encode('utf8'), None)


class Slug(Validator):
    """
    converts arbitrary text string to a slug::
    """

    def _urlify(self, s):
        """
        Converts incoming string to a simplified ASCII subset.
        if (keep_underscores): underscores are retained in the string
        else: underscores are translated to hyphens (default)
        """
        if isinstance(s, str):
            s = s.decode('utf-8')             # to unicode
        s = s.lower()                         # to lowercase
        s = unicodedata.normalize('NFKD', s)  # replace special characters
        s = s.encode('ascii', 'ignore')       # encode as ASCII
        s = re.sub('&\w+?;', '', s)           # strip html entities
        if self.keep_underscores:
            s = re.sub('\s+', '-', s)         # whitespace to hyphens
            s = re.sub('[^\w\-]', '', s)      # strip all but alphanumeric/underscore/hyphen
        else:
            s = re.sub('[\s_]+', '-', s)      # whitespace & underscores to hyphens
            s = re.sub('[^a-z0-9\-]', '', s)  # strip all but alphanumeric/hyphen
        s = re.sub('[-_][-_]+', '-', s)       # collapse strings of hyphens
        s = s.strip('-')                      # remove leading and trailing hyphens
        return s[:self.maxlen]                # enforce maximum length

    def __init__(self, maxlen=80, check=False, error_message='Must be slug',
                 keep_underscores=False):
        self.maxlen = maxlen
        self.check = check
        self.error_message = error_message
        self.keep_underscores = keep_underscores

    def __call__(self, value):
        if self.check and value != self._urlify(value):
            return (value, _translate(self.error_message))
        return (self._urlify(value), None)


class anyOf(Validator):
    """
    Tests if any of the validators in a list returns successfully::
    """

    def __init__(self, subs):
        self.subs = subs

    def __call__(self, value):
        for validator in self.subs:
            value, error = validator(value)
            if error is None:
                break
        return value, error

    def formatter(self, value):
        # Use the formatter of the first subvalidator
        # that validates the value and has a formatter
        for validator in self.subs:
            if hasattr(validator, 'formatter') and validator(value)[1] != None:
                return validator.formatter(value)


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
        value, empty = _is_empty(value, empty_regex=self.empty_regex)
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


class Cleanup(Validator):
    """
    removes special characters on validation
    """
    REGEX_CLEANUP = re.compile('[^\x09\x0a\x0d\x20-\x7e]')

    def __init__(self, regex=None):
        self.regex = self.REGEX_CLEANUP if regex is None \
            else re.compile(regex)

    def __call__(self, value):
        v = self.regex.sub('', str(value).strip())
        return (v, None)


class _LazyCrypt(object):
    """
    Stores a lazy password hash
    """
    def __init__(self, crypt, password):
        """
        crypt is an instance of the Crypt validator,
        password is the password as inserted by the user
        """
        self.crypt = crypt
        self.password = password
        self.crypted = None

    def __str__(self):
        """
        Encrypted self.password and caches it in self.crypted.
        If self.crypt.salt the output is in the format
        <algorithm>$<salt>$<hash>

        Try get the digest_alg from the key (if it exists)
        else assume the default digest_alg. If not key at all, set key=''

        If a salt is specified use it, if salt is True, set salt to uuid
        (this should all be backward compatible)

        Options:
        key = 'uuid'
        key = 'md5:uuid'
        key = 'sha512:uuid'
        ...
        key = 'pbkdf2(1000,64,sha512):uuid' 1000 iterations and 64 chars length
        """
        if self.crypted:
            return self.crypted
        if self.crypt.key:
            if ':' in self.crypt.key:
                digest_alg, key = self.crypt.key.split(':', 1)
            else:
                digest_alg, key = self.crypt.digest_alg, self.crypt.key
        else:
            digest_alg, key = self.crypt.digest_alg, ''
        if self.crypt.salt:
            if self.crypt.salt == True:
                salt = str(uuid()).replace('-', '')[-16:]
            else:
                salt = self.crypt.salt
        else:
            salt = ''
        hashed = simple_hash(self.password, key, salt, digest_alg)
        self.crypted = '%s$%s$%s' % (digest_alg, salt, hashed)
        return self.crypted

    def __eq__(self, stored_password):
        """
        compares the current lazy crypted password with a stored password
        """

        # _LazyCrypt objects comparison
        if isinstance(stored_password, self.__class__):
            return ((self is stored_password) or
                    ((self.crypt.key == stored_password.crypt.key) and
                    (self.password == stored_password.password)))

        if self.crypt.key:
            if ':' in self.crypt.key:
                key = self.crypt.key.split(':')[1]
            else:
                key = self.crypt.key
        else:
            key = ''
        if stored_password is None:
            return False
        elif stored_password.count('$') == 2:
            (digest_alg, salt, hash) = stored_password.split('$')
            h = simple_hash(self.password, key, salt, digest_alg)
            temp_pass = '%s$%s$%s' % (digest_alg, salt, h)
        else:  # no salting
            # guess digest_alg
            digest_alg = DIGEST_ALG_BY_SIZE.get(len(stored_password), None)
            if not digest_alg:
                return False
            else:
                temp_pass = simple_hash(self.password, key, '', digest_alg)
        return temp_pass == stored_password

    def __ne__(self, other):
        return not self.__eq__(other)


class Crypt(object):
    """
    encodes the value on validation with a digest.

    If no arguments are provided Crypt uses the MD5 algorithm.
    If the key argument is provided the HMAC+MD5 algorithm is used.
    If the digest_alg is specified this is used to replace the
    MD5 with, for example, SHA512. The digest_alg can be
    the name of a hashlib algorithm as a string or the algorithm itself.

    min_length is the minimal password length (default 4)
    error_message is the message if password is too short

    Notice that an empty password is accepted but invalid. It will not allow
    login back. Stores junk as hashed password.

    Specify an algorithm or by default we will use sha512.

    Typical available algorithms:
      md5, sha1, sha224, sha256, sha384, sha512

    If salt, it hashes a password with a salt.
    If salt is True, this method will automatically generate one.
    Either case it returns an encrypted password string with format:

      <algorithm>$<salt>$<hash>

    Important: hashed password is returned as a _LazyCrypt object and computed
    only if needed. The LasyCrypt object also knows how to compare itself with
    an existing salted password
    """

    def __init__(self,
                 key=None,
                 digest_alg='pbkdf2(1000,20,sha512)',
                 min_length=0,
                 error_message='Too short', salt=True,
                 max_length=1024):
        """
        important, digest_alg='md5' is not the default hashing algorithm for
        web2py. This is only an example of usage of this function.

        The actual hash algorithm is determined from the key which is
        generated by web2py in tools.py. This defaults to hmac+sha512.
        """
        self.key = key
        self.digest_alg = digest_alg
        self.min_length = min_length
        self.max_length = max_length
        self.error_message = error_message
        self.salt = salt

    def __call__(self, value):
        value = value and value[:self.max_length]
        if len(value) < self.min_length:
            return ('', _translate(self.error_message))
        return (_LazyCrypt(self, value), None)


class isStrong(object):
    """
    enforces complexity requirements on a field
    """
    lowerset = frozenset(unicode('abcdefghijklmnopqrstuvwxyz'))
    upperset = frozenset(unicode('ABCDEFGHIJKLMNOPQRSTUVWXYZ'))
    numberset = frozenset(unicode('0123456789'))
    sym1set = frozenset(unicode('!@#$%^&*()'))
    sym2set = frozenset(unicode('~`-_=+[]{}\\|;:\'",.<>?/'))
    otherset = frozenset(unicode('0123456789abcdefghijklmnopqrstuvwxyz'))

    def __init__(self, min=None, max=None, upper=None, lower=None, number=None,
                 entropy=None,
                 special=None, specials=r'~!@#$%^&*()_+-=?<>,.:;{}[]|',
                 invalid=' "', error_message=None, es=False):
        self.entropy = entropy
        if entropy is None:
            # enforce default requirements
            self.min = 8 if min is None else min
            self.max = max  # was 20, but that doesn't make sense
            self.upper = 1 if upper is None else upper
            self.lower = 1 if lower is None else lower
            self.number = 1 if number is None else number
            self.special = 1 if special is None else special
        else:
            # by default, an entropy spec is exclusive
            self.min = min
            self.max = max
            self.upper = upper
            self.lower = lower
            self.number = number
            self.special = special
        self.specials = specials
        self.invalid = invalid
        self.error_message = error_message
        self.estring = es   # return error message as string (for doctest)

    def __call__(self, value):
        failures = []
        if value and len(value) == value.count('*') > 4:
            return (value, None)
        if self.entropy is not None:
            entropy = isStrong.calc_entropy(value)
            if entropy < self.entropy:
                failures.append(
                    _translate(
                        "Entropy (%(have)s) less than required (%(need)s)")
                    % dict(have=entropy, need=self.entropy))
        if type(self.min) == int and self.min > 0:
            if not len(value) >= self.min:
                failures.append(_translate("Minimum length is %s") % self.min)
        if type(self.max) == int and self.max > 0:
            if not len(value) <= self.max:
                failures.append(_translate("Maximum length is %s") % self.max)
        if type(self.special) == int:
            all_special = [ch in value for ch in self.specials]
            if self.special > 0:
                if not all_special.count(True) >= self.special:
                    failures.append(
                        _translate(
                            "Must include at least %s of the following: %s")
                        % (self.special, self.specials))
        if self.invalid:
            all_invalid = [ch in value for ch in self.invalid]
            if all_invalid.count(True) > 0:
                failures.append(
                    _translate(
                        "May not contain any of the following: %s")
                    % self.invalid)
        if type(self.upper) == int:
            all_upper = re.findall("[A-Z]", value)
            if self.upper > 0:
                if not len(all_upper) >= self.upper:
                    failures.append(
                        _translate("Must include at least %s upper case")
                        % str(self.upper))
            else:
                if len(all_upper) > 0:
                    failures.append(
                        _translate("May not include any upper case letters"))
        if type(self.lower) == int:
            all_lower = re.findall("[a-z]", value)
            if self.lower > 0:
                if not len(all_lower) >= self.lower:
                    failures.append(
                        _translate("Must include at least %s lower case")
                        % str(self.lower))
            else:
                if len(all_lower) > 0:
                    failures.append(
                        _translate("May not include any lower case letters"))
        if type(self.number) == int:
            all_number = re.findall("[0-9]", value)
            if self.number > 0:
                numbers = "number"
                if self.number > 1:
                    numbers = "numbers"
                if not len(all_number) >= self.number:
                    failures.append(_translate("Must include at least %s %s")
                                    % (str(self.number), numbers))
            else:
                if len(all_number) > 0:
                    failures.append(_translate("May not include any numbers"))
        if len(failures) == 0:
            return (value, None)
        if not self.error_message:
            if self.estring:
                return (value, '|'.join(failures))
            from .templating import NOESCAPE
            return (value, NOESCAPE('<br />'.join(failures)))
        else:
            return (value, _translate(self.error_message))

    @staticmethod
    def calc_entropy(string):
        " calculates a simple entropy for a given string "
        import math
        alphabet = 0    # alphabet size
        other = set()
        seen = set()
        lastset = None
        if isinstance(string, str):
            string = unicode(string, encoding='utf8')
        for c in string:
            # classify this character
            inset = isStrong.otherset
            for cset in (isStrong.lowerset, isStrong.upperset,
                         isStrong.numberset, isStrong.sym1set,
                         isStrong.sym2set):
                if c in cset:
                    inset = cset
                    break
            # calculate effect of character on alphabet size
            if inset not in seen:
                seen.add(inset)
                alphabet += len(inset)  # credit for a new character set
            elif c not in other:
                alphabet += 1   # credit for unique characters
                other.add(c)
            if inset is not lastset:
                alphabet += 1   # credit for set transitions
                lastset = cset
        entropy = len(
            string) * math.log(alphabet) / 0.6931471805599453  # math.log(2)
        return round(entropy, 2)


class inSubSet(inSet):
    REGEX_W = re.compile('\w+')

    def __init__(self, *a, **b):
        inSet.__init__(self, *a, **b)

    def __call__(self, value):
        values = self.REGEX_W.findall(str(value))
        failures = [x for x in values if inSet.__call__(self, x)[1]]
        if failures:
            return (value, _translate(self.error_message))
        return (value, None)


class isImage(Validator):
    """
    Checks if file uploaded through file input was saved in one of selected
    image formats and has dimensions within given boundaries.

    Does *not* check for maximum file size (use hasLength for that). Returns
    validation failure if no data was uploaded.

    Supported file formats: BMP, GIF, JPEG, PNG.

    Code parts taken from
    http://mail.python.org/pipermail/python-list/2007-June/617126.html

    Args:
        extensions: iterable containing allowed *lowercase* image file
        extensions ('jpg' extension of uploaded file counts as 'jpeg')
        maxsize: iterable containing maximum width and height of the image
        minsize: iterable containing minimum width and height of the image

    Use (-1, -1) as minsize to pass image size check.
    """

    def __init__(self,
                 extensions=('bmp', 'gif', 'jpeg', 'png'),
                 maxsize=(10000, 10000),
                 minsize=(0, 0),
                 error_message='Invalid image'):

        self.extensions = extensions
        self.maxsize = maxsize
        self.minsize = minsize
        self.error_message = error_message

    def __call__(self, value):
        try:
            extension = value.filename.rfind('.')
            assert extension >= 0
            extension = value.filename[extension + 1:].lower()
            if extension == 'jpg':
                extension = 'jpeg'
            assert extension in self.extensions
            if extension == 'bmp':
                width, height = self.__bmp(value.file)
            elif extension == 'gif':
                width, height = self.__gif(value.file)
            elif extension == 'jpeg':
                width, height = self.__jpeg(value.file)
            elif extension == 'png':
                width, height = self.__png(value.file)
            else:
                width = -1
                height = -1
            assert self.minsize[0] <= width <= self.maxsize[0] \
                and self.minsize[1] <= height <= self.maxsize[1]
            value.file.seek(0)
            return (value, None)
        except:
            return (value, _translate(self.error_message))

    def __bmp(self, stream):
        if stream.read(2) == 'BM':
            stream.read(16)
            return struct.unpack("<LL", stream.read(8))
        return (-1, -1)

    def __gif(self, stream):
        if stream.read(6) in ('GIF87a', 'GIF89a'):
            stream = stream.read(5)
            if len(stream) == 5:
                return tuple(struct.unpack("<HHB", stream)[:-1])
        return (-1, -1)

    def __jpeg(self, stream):
        if stream.read(2) == '\xFF\xD8':
            while True:
                (marker, code, length) = struct.unpack("!BBH", stream.read(4))
                if marker != 0xFF:
                    break
                elif code >= 0xC0 and code <= 0xC3:
                    return tuple(reversed(
                        struct.unpack("!xHH", stream.read(5))))
                else:
                    stream.read(length - 2)
        return (-1, -1)

    def __png(self, stream):
        if stream.read(8) == '\211PNG\r\n\032\n':
            stream.read(4)
            if stream.read(4) == "IHDR":
                return struct.unpack("!LL", stream.read(8))
        return (-1, -1)


class FilenameMatches(Validator):
    """
    Checks if name and extension of file uploaded through file input matches
    given criteria.

    Does *not* ensure the file type in any way. Returns validation failure
    if no data was uploaded.

    Args:
        filename: filename (before dot) regex
        extension: extension (after dot) regex
        lastdot: which dot should be used as a filename / extension separator:
            True means last dot, eg. file.png -> file / png
            False means first dot, eg. file.tar.gz -> file / tar.gz
        case:
            0 - keep the case,
            1 - transform the string into lowercase (default),
            2 - transform the string into uppercase

    If there is no dot present, extension checks will be done against empty
    string and filename checks against whole value.
    """

    def __init__(self, filename=None, extension=None, lastdot=True, case=1,
                 error_message='Enter valid filename'):
        if isinstance(filename, str):
            filename = re.compile(filename)
        if isinstance(extension, str):
            extension = re.compile(extension)
        self.filename = filename
        self.extension = extension
        self.lastdot = lastdot
        self.case = case
        self.error_message = error_message

    def __call__(self, value):
        try:
            string = value.filename
        except:
            return (value, _translate(self.error_message))
        if self.case == 1:
            string = string.lower()
        elif self.case == 2:
            string = string.upper()
        if self.lastdot:
            dot = string.rfind('.')
        else:
            dot = string.find('.')
        if dot == -1:
            dot = len(string)
        if self.filename and not self.filename.match(string[:dot]):
            return (value, _translate(self.error_message))
        elif self.extension and not self.extension.match(string[dot + 1:]):
            return (value, _translate(self.error_message))
        else:
            return (value, None)


class isIPv4(Validator):
    """
    Checks if field's value is an IP version 4 address in decimal form. Can
    be set to force addresses from certain range.

    IPv4 regex taken from: http://regexlib.com/REDetails.aspx?regexp_id=1411

    Args:
        minip: lowest allowed address; accepts:

            - str, eg. 192.168.0.1
            - list or tuple of octets, eg. [192, 168, 0, 1]
        maxip: highest allowed address; same as above
        invert: True to allow addresses only from outside of given range; note
            that range boundaries are not matched this way
        is_localhost: localhost address treatment:
            - None (default): indifferent
            - True (enforce): query address must match localhost address
            - False (forbid): query address must not match localhost address
        is_private: same as above, except that query address is checked against
            two address ranges: 172.16.0.0 - 172.31.255.255 and
            192.168.0.0 - 192.168.255.255
        is_automatic: same as above, except that query address is checked
            against one address range: 169.254.0.0 - 169.254.255.255

    Minip and maxip may also be lists or tuples of addresses in all above
    forms (str, int, list / tuple), allowing setup of multiple address ranges::

        minip = (minip1, minip2, ... minipN)
                   |       |           |
                   |       |           |
        maxip = (maxip1, maxip2, ... maxipN)

    Longer iterable will be truncated to match length of shorter one.
    """

    regex = re.compile('^(([1-9]?\d|1\d\d|2[0-4]\d|25[0-5])\.){3}([1-9]?\d|1\d\d|2[0-4]\d|25[0-5])$')
    numbers = (16777216, 65536, 256, 1)
    localhost = 2130706433
    private = ((2886729728L, 2886795263L), (3232235520L, 3232301055L))
    automatic = (2851995648L, 2852061183L)

    def __init__(
        self,
        minip='0.0.0.0',
        maxip='255.255.255.255',
        invert=False,
        is_localhost=None,
        is_private=None,
        is_automatic=None,
            error_message='Enter valid IPv4 address'):
        for n, value in enumerate((minip, maxip)):
            temp = []
            if isinstance(value, str):
                temp.append(value.split('.'))
            elif isinstance(value, (list, tuple)):
                if len(value) == len(filter(
                        lambda item: isinstance(item, int), value)) == 4:
                    temp.append(value)
                else:
                    for item in value:
                        if isinstance(item, str):
                            temp.append(item.split('.'))
                        elif isinstance(item, (list, tuple)):
                            temp.append(item)
            numbers = []
            for item in temp:
                number = 0
                for i, j in zip(self.numbers, item):
                    number += i * int(j)
                numbers.append(number)
            if n == 0:
                self.minip = numbers
            else:
                self.maxip = numbers
        self.invert = invert
        self.is_localhost = is_localhost
        self.is_private = is_private
        self.is_automatic = is_automatic
        self.error_message = error_message

    def __call__(self, value):
        if self.regex.match(value):
            number = 0
            for i, j in zip(self.numbers, value.split('.')):
                number += i * int(j)
            ok = False
            for bottom, top in zip(self.minip, self.maxip):
                if self.invert != (bottom <= number <= top):
                    ok = True
            if not (self.is_localhost is None or self.is_localhost ==
                    (number == self.localhost)):
                    ok = False
            if not (self.is_private is None or self.is_private ==
                    (sum([number[0] <= number <= number[1]
                     for number in self.private]) > 0)):
                    ok = False
            if not (self.is_automatic is None or self.is_automatic ==
                    (self.automatic[0] <= number <= self.automatic[1])):
                    ok = False
            if ok:
                return (value, None)
        return (value, _translate(self.error_message))


class isIPv6(Validator):
    """
    Checks if field's value is an IP version 6 address. First attempts to
    use the ipaddress library and falls back to contrib/ipaddr.py from Google
    (https://code.google.com/p/ipaddr-py/)

    Args:
        is_private: None (default): indifferent
                    True (enforce): address must be in fc00::/7 range
                    False (forbid): address must NOT be in fc00::/7 range
        is_link_local: Same as above but uses fe80::/10 range
        is_reserved: Same as above but uses IETF reserved range
        is_mulicast: Same as above but uses ff00::/8 range
        is_routeable: Similar to above but enforces not private, link_local,
                      reserved or multicast
        is_6to4: Same as above but uses 2002::/16 range
        is_teredo: Same as above but uses 2001::/32 range
        subnets: value must be a member of at least one from list of subnets
    """

    def __init__(self, is_private=None, is_link_local=None, is_reserved=None,
                 is_multicast=None, is_routeable=None, is_6to4=None,
                 is_teredo=None, subnets=None,
                 error_message='Enter valid IPv6 address'):
        self.is_private = is_private
        self.is_link_local = is_link_local
        self.is_reserved = is_reserved
        self.is_multicast = is_multicast
        self.is_routeable = is_routeable
        self.is_6to4 = is_6to4
        self.is_teredo = is_teredo
        self.subnets = subnets
        self.error_message = error_message

    def __call__(self, value):
        try:
            import ipaddress
        except ImportError:
            raise RuntimeError(
                "You need 'ipaddress' python module to use isIPv6 validator.")

        try:
            ip = ipaddress.IPv6Address(value)
            ok = True
        except ipaddress.AddressValueError:
            return (value, _translate(self.error_message))

        if self.subnets:
            # iterate through self.subnets to see if value is a member
            ok = False
            if isinstance(self.subnets, str):
                self.subnets = [self.subnets]
            for network in self.subnets:
                try:
                    ipnet = ipaddress.IPv6Network(network)
                except (ipaddress.NetmaskValueError, ipaddress.AddressValueError):
                    return (value, _translate('invalid subnet provided'))
                if ip in ipnet:
                    ok = True

        if self.is_routeable:
            self.is_private = False
            self.is_link_local = False
            self.is_reserved = False
            self.is_multicast = False

        if not (self.is_private is None or self.is_private ==
                ip.is_private):
            ok = False
        if not (self.is_link_local is None or self.is_link_local ==
                ip.is_link_local):
            ok = False
        if not (self.is_reserved is None or self.is_reserved ==
                ip.is_reserved):
            ok = False
        if not (self.is_multicast is None or self.is_multicast ==
                ip.is_multicast):
            ok = False
        if not (self.is_6to4 is None or self.is_6to4 ==
                ip.is_6to4):
            ok = False
        if not (self.is_teredo is None or self.is_teredo ==
                ip.is_teredo):
            ok = False

        if ok:
            return (value, None)

        return (value, _translate(self.error_message))


class isIP(Validator):
    """
    Checks if field's value is an IP Address (v4 or v6). Can be set to force
    addresses from within a specific range. Checks are done with the correct
    isIPv4 and isIPv6 validators.

    Uses ipaddress library if found, falls back to PEP-3144 ipaddr.py from
    Google (in contrib).

    Args:
        minip: lowest allowed address; accepts:
               str, eg. 192.168.0.1
               list or tuple of octets, eg. [192, 168, 0, 1]
        maxip: highest allowed address; same as above
        invert: True to allow addresses only from outside of given range; note
                that range boundaries are not matched this way

    IPv4 specific arguments:

        - is_localhost: localhost address treatment:
            - None (default): indifferent
            - True (enforce): query address must match localhost address
              (127.0.0.1)
            - False (forbid): query address must not match localhost address
        - is_private: same as above, except that query address is checked
          against two address ranges: 172.16.0.0 - 172.31.255.255 and
          192.168.0.0 - 192.168.255.255
        - is_automatic: same as above, except that query address is checked
          against one address range: 169.254.0.0 - 169.254.255.255
        - is_ipv4: either:
            - None (default): indifferent
            - True (enforce): must be an IPv4 address
            - False (forbid): must NOT be an IPv4 address

    IPv6 specific arguments:

        - is_link_local: Same as above but uses fe80::/10 range
        - is_reserved: Same as above but uses IETF reserved range
        - is_mulicast: Same as above but uses ff00::/8 range
        - is_routeable: Similar to above but enforces not private, link_local,
          reserved or multicast
        - is_6to4: Same as above but uses 2002::/16 range
        - is_teredo: Same as above but uses 2001::/32 range
        - subnets: value must be a member of at least one from list of subnets
        - is_ipv6: either:

            - None (default): indifferent
            - True (enforce): must be an IPv6 address
            - False (forbid): must NOT be an IPv6 address

    Minip and maxip may also be lists or tuples of addresses in all above
    forms (str, int, list / tuple), allowing setup of multiple address ranges::

        minip = (minip1, minip2, ... minipN)
                   |       |           |
                   |       |           |
        maxip = (maxip1, maxip2, ... maxipN)

    Longer iterable will be truncated to match length of shorter one.
    """

    def __init__(self, minip='0.0.0.0', maxip='255.255.255.255', invert=False,
                 is_localhost=None, is_private=None, is_automatic=None,
                 is_ipv4=None, is_link_local=None, is_reserved=None,
                 is_multicast=None, is_routeable=None, is_6to4=None,
                 is_teredo=None, subnets=None, is_ipv6=None,
                 error_message='Enter valid IP address'):
        self.minip = minip,
        self.maxip = maxip,
        self.invert = invert
        self.is_localhost = is_localhost
        self.is_private = is_private
        self.is_automatic = is_automatic
        self.is_ipv4 = is_ipv4
        self.is_private = is_private
        self.is_link_local = is_link_local
        self.is_reserved = is_reserved
        self.is_multicast = is_multicast
        self.is_routeable = is_routeable
        self.is_6to4 = is_6to4
        self.is_teredo = is_teredo
        self.subnets = subnets
        self.is_ipv6 = is_ipv6
        self.error_message = error_message

    def __call__(self, value):
        try:
            import ipaddress
        except ImportError:
            raise RuntimeError(
                "You need 'ipaddress' python module to use isIP validator.")

        try:
            ip = ipaddress.ip_address(value)
        except ValueError:
            return (value, _translate(self.error_message))

        if self.is_ipv4 and isinstance(ip, ipaddress.IPv6Address):
            retval = (value, _translate(self.error_message))
        elif self.is_ipv6 and isinstance(ip, ipaddress.IPv4Address):
            retval = (value, _translate(self.error_message))
        elif self.is_ipv4 or isinstance(ip, ipaddress.IPv4Address):
            retval = isIPv4(
                minip=self.minip,
                maxip=self.maxip,
                invert=self.invert,
                is_localhost=self.is_localhost,
                is_private=self.is_private,
                is_automatic=self.is_automatic,
                error_message=self.error_message
                )(value)
        elif self.is_ipv6 or isinstance(ip, ipaddress.IPv6Address):
            retval = isIPv6(
                is_private=self.is_private,
                is_link_local=self.is_link_local,
                is_reserved=self.is_reserved,
                is_multicast=self.is_multicast,
                is_routeable=self.is_routeable,
                is_6to4=self.is_6to4,
                is_teredo=self.is_teredo,
                subnets=self.subnets,
                error_message=self.error_message
                )(value)
        else:
            retval = (value, _translate(self.error_message))

        return retval
