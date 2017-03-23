# -*- coding: utf-8 -*-
"""
    weppy.validators.consist
    ------------------------

    Validators that check the value is of a certain type.

    :copyright: (c) 2014-2017 by Giovanni Barillari

    Based on the web2py's validators (http://www.web2py.com)
    :copyright: (c) by Massimo Di Pierro <mdipierro@cs.depaul.edu>

    :license: LGPLv3 (http://www.gnu.org/licenses/lgpl.html)
"""

import decimal
import json
import re
import struct
from datetime import date, time, datetime, timedelta
from time import strptime
from .._compat import PY2, basestring, string_types
from ..serializers import Serializers
from ..utils import parse_datetime
from .basic import Validator, ParentValidator, _is, Matches
from .helpers import translate, _UTC, url_split_regex, official_url_schemes, \
    unofficial_url_schemes, unicode_to_ascii_url, official_top_level_domains, \
    _DEFAULT

if PY2:
    from urllib import unquote as url_unquote
else:
    from urllib.parse import unquote as url_unquote

_utc = _UTC()


class isInt(_is):
    rule = re.compile('^[+-]?\d+$')

    def check(self, value):
        return int(value), None


class isFloat(_is):
    def __init__(self, dot=".", message=None):
        _is.__init__(self, message)
        self.dot = dot

    def check(self, value):
        try:
            v = float(str(value).replace(self.dot, '.'))
            return v, None
        except (ValueError, TypeError):
            pass
        return value, translate(self.message)

    def _str2dec(number):
        s = str(number)
        if '.' not in s:
            s += '.00'
        else:
            s += '0' * (2 - len(s.split('.')[1]))
        return s

    def formatter(self, value):
        if value is None:
            return None
        val = str(value)
        if '.' not in val:
            val += '.00'
        else:
            val += '0' * (2 - len(val.split('.')[1]))
        return val.replace('.', self.dot)


class isDecimal(isFloat):
    def check(self, value):
        try:
            if isinstance(value, decimal.Decimal):
                v = value
            else:
                v = decimal.Decimal(str(value).replace(self.dot, '.'))
            return v, None
        except (ValueError, TypeError, decimal.InvalidOperation):
            return value, translate(self.message)


class isTime(_is):
    rule = re.compile('((?P<h>[0-9]+))([^0-9 ]+(?P<m>[0-9 ]+))?([^0-9ap ]+' +
                      '(?P<s>[0-9]*))?((?P<d>[ap]m))?')

    def __call__(self, value):
        return _is.__call__(self, value.lower() if value else value)

    def check(self, value):
        val = self.rule.match(value)
        try:
            (h, m, s) = (int(val.group('h')), 0, 0)
            if not val.group('m') is None:
                m = int(val.group('m'))
            if not val.group('s') is None:
                s = int(val.group('s'))
            if val.group('d') == 'pm' and 0 < h < 12:
                h = h + 12
            if val.group('d') == 'am' and h == 12:
                h = 0
            if not (h in range(24) and m in range(60) and s
                    in range(60)):
                raise ValueError(
                    'Hours or minutes or seconds are outside of allowed range')
            val = time(h, m, s)
            return val, None
        except AttributeError:
            pass
        except ValueError:
            pass
        return value, translate(self.message)


class isDate(_is):
    def __init__(self, format='%Y-%m-%d', timezone=None, message=None):
        _is.__init__(self, message)
        self.format = translate(format)
        self.timezone = timezone
        self.extremes = {}

    def _parse(self, value):
        (y, m, d, hh, mm, ss, t0, t1, t2) = \
            strptime(value, str(self.format))
        return date(y, m, d)

    def _check_instance(self, value):
        return isinstance(value, date)

    def check(self, value):
        if self._check_instance(value):
            if self.timezone is not None:
                value = value - timedelta(seconds=self.timezone * 3600)
            return value, None
        try:
            val = self._parse(value)
            if self.timezone is not None:
                val = self.timezone.localize(val).astimezone(_utc)
            return val, None
        except:
            self.extremes.update(isDate.nice(self.format))
            return value, translate(self.message) % self.extremes

    def _formatter_obj(self, value):
        return datetime(value.year, value.month, value.day)

    def formatter(self, value):
        if value is None:
            return None
        d = self._formatter_obj(value)
        if self.timezone is not None:
            d = d.replace(tzinfo=_utc).astimezone(self.timezone)
        return d.strftime(str(self.format))

    @staticmethod
    def nice(format):
        codes = (
            ('%Y', '1963'), ('%y', '63'), ('%d', '28'), ('%m', '08'),
            ('%b', 'Aug'), ('%B', 'August'), ('%H', '14'), ('%I', '02'),
            ('%p', 'PM'), ('%M', '30'), ('%S', '59')
        )
        for (a, b) in codes:
            format = format.replace(a, b)
        return dict(format=format)


class isDatetime(isDate):
    def __init__(self, format=_DEFAULT, **kwargs):
        self._parse, format = self._get_parser(format)
        isDate.__init__(self, format=format, **kwargs)

    def _get_parser(self, format):
        if format is _DEFAULT:
            return self._parse_pendulum, '%Y-%m-%dT%H:%M:%S'
        return self._parse_strptime, format

    def _parse_strptime(self, value):
        (y, m, d, hh, mm, ss, t0, t1, t2) = \
            strptime(value, str(self.format))
        return datetime(y, m, d, hh, mm, ss)

    def _parse_pendulum(self, value):
        return parse_datetime(value).in_timezone('UTC')

    def _check_instance(self, value):
        return isinstance(value, datetime)

    def _formatter_obj(self, value):
        return datetime(
            value.year, value.month, value.day,
            value.hour, value.minute, value.second)


class isEmail(_is):
    rule = re.compile(
        "^(?!\.)([-a-z0-9!\#$%&'*+/=?^_`{|}~]|(?<!\.)\.)+(?<!\.)@" +
        "(localhost|([a-z0-9]([-\w]*[a-z0-9])?\.)+[a-z]{2,})$",
        re.VERBOSE | re.IGNORECASE
    )

    def __init__(self, banned=None, forced=None, message=None):
        _is.__init__(self, message)
        self.banned = banned
        self.forced = forced

    def check(self, value):
        domain = value.split('@')[1]
        if (
            (not self.banned or not self.banned.match(domain)) and
            (not self.forced or self.forced.match(domain))
        ):
            return value, None
        return value, translate(self.message)


class isList(ParentValidator):
    def __init__(self, children, splitter=None, message=None):
        ParentValidator.__init__(self, children, message)
        self.splitter = None
        if splitter:
            self.splitter = re.compile('[^' + splitter + '\s]+')

    def __call__(self, value):
        if self.splitter is not None and isinstance(value, basestring):
            values = self.splitter.findall(value)
        else:
            if not isinstance(value, list):
                values = [value]
            else:
                values = value
            values = [val for val in values if str(val).strip()]
        nvals = []
        for val in values:
            v = val
            for child in self.children:
                v, e = child(v)
                if e:
                    return val, e
            nvals.append(v)
        values = nvals
        return values, None


class isJSON(_is):
    JSONErrors = (NameError, TypeError, ValueError, AttributeError,
                  KeyError)

    def check(self, value):
        if isinstance(value, string_types):
            try:
                v = json.loads(value)
                return v, None
            except self.JSONErrors:
                return value, translate(self.message)
        if not isinstance(value, (dict, list)):
            return value, translate(self.message)
        try:
            Serializers.get_for('json')(value)
        except self.JSONErrors:
            return value, translate(self.message)
        return value, None

    def formatter(self, value):
        if value is None:
            return None
        return json.dumps(value)


class isAlphanumeric(Matches):
    message = 'Enter only letters, numbers, and underscores'

    def __init__(self, message=None):
        Matches.__init__(self, '^[\w]*$', message=message)


class isImage(Validator):
    # Checks if file uploaded through file input was saved in one of selected
    # image formats and has dimensions within given boundaries.
    message = "Invalid image"

    def __init__(self, extensions=('bmp', 'gif', 'jpeg', 'png'),
                 width={'min': 0, 'max': 10000},
                 height={'min': 0, 'max': 100000}, message=None):
        Validator.__init__(self, message)
        self.extensions = extensions
        self.maxsize = (width.get('max', 10000), height.get('max', 10000))
        self.minsize = (width.get('min', 0), height.get('min', 0))
        self.message = message

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
            return value, None
        except:
            return value, translate(self.message)

    def __bmp(self, stream):
        if stream.read(2) == 'BM':
            stream.read(16)
            return struct.unpack("<LL", stream.read(8))
        return -1, -1

    def __gif(self, stream):
        if stream.read(6) in ('GIF87a', 'GIF89a'):
            stream = stream.read(5)
            if len(stream) == 5:
                return tuple(struct.unpack("<HHB", stream)[:-1])
        return -1, -1

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
        return -1, -1

    def __png(self, stream):
        if stream.read(8) == '\211PNG\r\n\032\n':
            stream.read(4)
            if stream.read(4) == "IHDR":
                return struct.unpack("!LL", stream.read(8))
        return -1, -1


class _isGenericUrl(Validator):
    """
    Rejects a URL string if any of the following is true:
       * The string is empty or None
       * The string uses characters that are not allowed in a URL
       * The URL scheme specified (if one is specified) is not valid

    Based on RFC 2396: http://www.faqs.org/rfcs/rfc2396.html
    @author: Jonathan Benn
    """
    message = "Invalid URL"
    all_url_schemes = [None] + official_url_schemes + unofficial_url_schemes

    def __init__(self, schemes=None, prepend_scheme=None, message=None):
        Validator.__init__(self, message)
        self.allowed_schemes = schemes or self.all_url_schemes
        self.prepend_scheme = prepend_scheme
        if self.prepend_scheme not in self.allowed_schemes:
            raise SyntaxError(
                "prepend_scheme='%s' is not in allowed_schemes=%s" %
                (self.prepend_scheme, self.allowed_schemes))

    GENERIC_URL = re.compile(
        r"%[^0-9A-Fa-f]{2}|%[^0-9A-Fa-f][0-9A-Fa-f]|%[0-9A-Fa-f][^0-9A-Fa-f]|%$|%[0-9A-Fa-f]$|%[^0-9A-Fa-f]$")
    GENERIC_URL_VALID = re.compile(r"[A-Za-z0-9;/?:@&=+$,\-_\.!~*'\(\)%#]+$")

    def __call__(self, value):
        try:
            # if the URL does not misuse the '%' character
            if not self.GENERIC_URL.search(value):
                # if the URL is only composed of valid characters
                if self.GENERIC_URL_VALID.match(value):
                    # Then split up the URL into its components and check on
                    # the scheme
                    scheme = url_split_regex.match(value).group(2)
                    # Clean up the scheme before we check it
                    if scheme is not None:
                        scheme = url_unquote(scheme).lower()
                    # If the scheme really exists
                    if scheme in self.allowed_schemes:
                        # Then the URL is valid
                        return value, None
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
                                    return value, None
        except:
            pass
        # else the URL is not valid
        return value, translate(self.message)


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
    @author: Jonathan Benn
    """
    message = "Invalid URL"
    http_schemes = [None, 'http', 'https']
    GENERIC_VALID_IP = re.compile(
        "([\w.!~*'|;:&=+$,-]+@)?\d+\.\d+\.\d+\.\d+(:\d*)*$")
    GENERIC_VALID_DOMAIN = re.compile(
        "([\w.!~*'|;:&=+$,-]+@)?(([A-Za-z0-9]+[A-Za-z0-9\-]*[A-Za-z0-9]+\.)" +
        "*([A-Za-z0-9]+\.)*)*([A-Za-z]+[A-Za-z0-9\-]*[A-Za-z0-9]+)\.?(:\d*)*$")

    def __init__(self, schemes=None, prepend_scheme='http', tlds=None,
                 message=None):
        Validator.__init__(self, message)
        self.allowed_schemes = schemes or self.http_schemes
        self.allowed_tlds = tlds or official_top_level_domains
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
        try:
            # if the URL passes generic validation
            x = _isGenericUrl(
                schemes=self.allowed_schemes,
                prepend_scheme=self.prepend_scheme, message=self.message
            )
            if x(value)[1] is None:
                componentsMatch = url_split_regex.match(value)
                authority = componentsMatch.group(4)
                # if there is an authority component
                if authority:
                    # if authority is a valid IP address
                    if self.GENERIC_VALID_IP.match(authority):
                        # Then this HTTP URL is valid
                        return value, None
                    else:
                        # else if authority is a valid domain name
                        domainMatch = self.GENERIC_VALID_DOMAIN.match(
                            authority)
                        if domainMatch:
                            # if the top-level domain really exists
                            if domainMatch.group(5).lower()\
                                    in self.allowed_tlds:
                                # Then this HTTP URL is valid
                                return value, None
                else:
                    # else this is a relative/abbreviated URL, which will parse
                    # into the URL's path component
                    path = componentsMatch.group(5)
                    # relative case: if this is a valid path (if it starts with
                    # a slash)
                    if path.startswith('/'):
                        # Then this HTTP URL is valid
                        return value, None
                    else:
                        # abbreviated case: if we haven't already, prepend a
                        # scheme and see if it fixes the problem
                        if value.find('://') < 0:
                            schemeToUse = self.prepend_scheme or 'http'
                            prependTest = self(schemeToUse + '://' + value)
                            # if the prepend test succeeded
                            if prependTest[1] is None:
                                # if prepending in the output is enabled
                                if self.prepend_scheme:
                                    return prependTest
                                else:
                                    # else return the original, non-prepended
                                    # value
                                    return value, None
        except:
            pass
        # else the HTTP URL is not valid
        return value, translate(self.message)


class isUrl(Validator):
    #: use `_isGenericUrl` and `_isHTTPUrl` depending on `mode` parameter
    message = "Invalid URL"

    def __init__(self, mode='http', schemes=None, prepend_scheme='http',
                 tlds=None, message=None):
        Validator.__init__(self, message)
        self.mode = mode.lower()
        if self.mode not in ['generic', 'http']:
            raise SyntaxError("invalid mode '%s' in isUrl" % self.mode)
        self.allowed_tlds = tlds
        self.allowed_schemes = schemes
        if self.allowed_schemes:
            if prepend_scheme not in self.allowed_schemes:
                raise SyntaxError(
                    "prepend_scheme='%s' is not in allowed_schemes=%s"
                    % (prepend_scheme, self.allowed_schemes))
        # if allowed_schemes is None, then we will defer testing
        # prepend_scheme's validity to a sub-method
        self.prepend_scheme = prepend_scheme

    def __call__(self, value):
        if self.mode == 'generic':
            subValidator = _isGenericUrl(
                schemes=self.allowed_schemes,
                prepend_scheme=self.prepend_scheme, message=self.message
            )
        elif self.mode == 'http':
            subValidator = _isHTTPUrl(
                schemes=self.allowed_schemes,
                prepend_scheme=self.prepend_scheme, tlds=self.allowed_tlds,
                message=self.message
            )
        else:
            raise SyntaxError("invalid mode '%s' in isUrl" % self.mode)

        # TODO: find a better solution
        if not PY2:
            return subValidator(value)
        #
        if isinstance(value, unicode):
            return subValidator(value)
        else:
            try:
                asciiValue = unicode_to_ascii_url(value, self.prepend_scheme)
            except Exception:
                #If we are not able to convert the unicode url into a
                # US-ASCII URL, then the URL is not valid
                return value, translate(self.message)

            rv = subValidator(asciiValue)
            #if the validation of the US-ASCII version of the value failed
            if not rv[1] is None:
                # then return the original input value, not the US-ASCII
                return value, rv[1]
            else:
                return rv


class isIPv4(Validator):
    """
    Checks if field's value is an IP version 4 address in decimal form. Can
    be set to force addresses from certain range.

    IPv4 regex taken from: http://regexlib.com/REDetails.aspx?regexp_id=1411

    Args:
        min: lowest allowed address; accepts:
            - str, eg. 192.168.0.1
            - list or tuple of octets, eg. [192, 168, 0, 1]
        max: highest allowed address; same as above
        invert: True to allow addresses only from outside of given range; note
            that range boundaries are not matched this way
        localhost: localhost address treatment:
            - None (default): indifferent
            - True (enforce): query address must match localhost address
            - False (forbid): query address must not match localhost address
        private: same as above, except that query address is checked against
            two address ranges: 172.16.0.0 - 172.31.255.255 and
            192.168.0.0 - 192.168.255.255
        automatic: same as above, except that query address is checked
            against one address range: 169.254.0.0 - 169.254.255.255

    Minip and maxip may also be lists or tuples of addresses in all above
    forms (str, int, list / tuple), allowing setup of multiple address ranges::
        minip = (minip1, minip2, ... minipN)
                   |       |           |
                   |       |           |
        maxip = (maxip1, maxip2, ... maxipN)

    Longer iterable will be truncated to match length of shorter one.
    """
    message = 'Invalid IPv4 address'
    regex = re.compile(
        '^(([1-9]?\d|1\d\d|2[0-4]\d|25[0-5])\.){3}([1-9]?\d|1\d\d|2[0-4]\d|25[0-5])$')
    numbers = (16777216, 65536, 256, 1)
    localhost = 2130706433
    private = ((2886729728, 2886795263), (3232235520, 3232301055))
    automatic = (2851995648, 2852061183)

    def __init__(self, min='0.0.0.0', max='255.255.255.255', invert=False,
                 localhost=None, private=None, auto=None, message=None):
        Validator.__init__(self, message)
        for n, value in enumerate((min, max)):
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
        self.is_localhost = localhost
        self.is_private = private
        self.is_automatic = auto

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
                     for number in self.private]) > 0)):  # NOQA
                    ok = False
            if not (self.is_automatic is None or self.is_automatic ==
                    (self.automatic[0] <= number <= self.automatic[1])):
                    ok = False
            if ok:
                return value, None
        return value, translate(self.message)


class isIPv6(Validator):
    """
    Checks if field's value is an IP version 6 address.
    Use the ipaddress library.

    Args:
        private: None (default): indifferent
                 True (enforce): address must be in fc00::/7 range
                 False (forbid): address must NOT be in fc00::/7 range
        link_local: Same as above but uses fe80::/10 range
        reserved: Same as above but uses IETF reserved range
        mulicast: Same as above but uses ff00::/8 range
        routeable: Similar to above but enforces not private, link_local,
                   reserved or multicast
        to4: Same as above but uses 2002::/16 range
        teredo: Same as above but uses 2001::/32 range
        subnets: value must be a member of at least one from list of subnets
    """
    message = 'Invalid IPv6 address'

    def __init__(self, private=None, link_local=None, reserved=None,
                 multicast=None, routeable=None, to4=None, teredo=None,
                 subnets=None, message=None):
        Validator.__init__(self, message)
        self.is_private = private
        self.is_link_local = link_local
        self.is_reserved = reserved
        self.is_multicast = multicast
        self.is_routeable = routeable
        self.is_6to4 = to4
        self.is_teredo = teredo
        self.subnets = subnets

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
            return (value, translate(self.message))

        if self.subnets:
            # iterate through self.subnets to see if value is a member
            ok = False
            if isinstance(self.subnets, str):
                self.subnets = [self.subnets]
            for network in self.subnets:
                try:
                    ipnet = ipaddress.IPv6Network(network)
                except (ipaddress.NetmaskValueError,
                        ipaddress.AddressValueError):
                    return value, translate('invalid subnet provided')
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
            return value, None

        return value, translate(self.message)


class isIP(Validator):
    """
    Checks if field's value is an IP Address (v4 or v6). Can be set to force
    addresses from within a specific range. Checks are done with the correct
    isIPv4 and isIPv6 validators.

    Uses ipaddress library.
    """
    message = 'Invalid IP address'

    def __init__(self, min='0.0.0.0', max='255.255.255.255', invert=False,
                 localhost=None, private=None, automatic=None, ipv4=None,
                 link_local=None, reserved=None, multicast=None,
                 routeable=None, to4=None, teredo=None, subnets=None,
                 ipv6=None, message=None):
        Validator.__init__(self, message)
        self.minip = min,
        self.maxip = max,
        self.invert = invert
        self.is_localhost = localhost
        self.is_private = private
        self.is_automatic = automatic
        self.is_ipv4 = ipv4
        self.is_private = private
        self.is_link_local = link_local
        self.is_reserved = reserved
        self.is_multicast = multicast
        self.is_routeable = routeable
        self.is_6to4 = to4
        self.is_teredo = teredo
        self.subnets = subnets
        self.is_ipv6 = ipv6

    def __call__(self, value):
        try:
            import ipaddress
        except ImportError:
            raise RuntimeError(
                "You need 'ipaddress' python module to use isIP validator."
            )

        try:
            ip = ipaddress.ip_address(value)
        except ValueError:
            return value, translate(self.message)

        if self.is_ipv4 and isinstance(ip, ipaddress.IPv6Address):
            rv = (value, translate(self.message))
        elif self.is_ipv6 and isinstance(ip, ipaddress.IPv4Address):
            rv = (value, translate(self.message))
        elif self.is_ipv4 or isinstance(ip, ipaddress.IPv4Address):
            rv = isIPv4(
                min=self.minip,
                max=self.maxip,
                invert=self.invert,
                localhost=self.is_localhost,
                private=self.is_private,
                automatic=self.is_automatic,
                message=self.message
            )(value)
        elif self.is_ipv6 or isinstance(ip, ipaddress.IPv6Address):
            rv = isIPv6(
                private=self.is_private,
                link_local=self.is_link_local,
                reserved=self.is_reserved,
                multicast=self.is_multicast,
                routeable=self.is_routeable,
                to4=self.is_6to4,
                teredo=self.is_teredo,
                subnets=self.subnets,
                message=self.message
            )(value)
        else:
            rv = (value, translate(self.message))
        return rv
