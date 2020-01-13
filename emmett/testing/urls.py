# -*- coding: utf-8 -*-
"""
    emmett.testing.urls
    -------------------

    Provides url helpers for testing suite.

    :copyright: 2014 Giovanni Barillari

    Several parts of this code comes from Werkzeug.
    :copyright: (c) 2015 by Armin Ronacher.

    :license: BSD-3-Clause
"""

import os
import re

from collections import namedtuple

# TODO: check conversions
from .._shortcuts import to_unicode
from ..datastructures import sdict


_always_safe = (
    b'abcdefghijklmnopqrstuvwxyz'
    b'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-+')
_hexdigits = '0123456789ABCDEFabcdef'
_hextobyte = dict(
    ((a + b).encode(), int(a + b, 16))
    for a in _hexdigits for b in _hexdigits
)

_scheme_re = re.compile(r'^[a-zA-Z0-9+-.]+$')

_URLTuple = namedtuple(
    '_URLTuple',
    ['scheme', 'netloc', 'path', 'query', 'fragment'])


class BaseURL(_URLTuple):
    __slots__ = ()

    def replace(self, **kwargs):
        return self._replace(**kwargs)

    @property
    def host(self):
        return self._split_host()[0]

    @property
    def ascii_host(self):
        rv = self.host
        if rv is not None and isinstance(rv, str):
            try:
                rv = _encode_idna(rv)
            except UnicodeError:
                rv = rv.encode('ascii', 'ignore')
        return to_unicode(rv, 'ascii', 'ignore')

    @property
    def port(self):
        try:
            rv = int(to_unicode(self._split_host()[1]))
            if 0 <= rv <= 65535:
                return rv
        except (ValueError, TypeError):
            pass

    @property
    def auth(self):
        return self._split_netloc()[0]

    @property
    def username(self):
        rv = self._split_auth()[0]
        if rv is not None:
            return url_unquote(rv)

    @property
    def raw_username(self):
        return self._split_auth()[0]

    @property
    def password(self):
        rv = self._split_auth()[1]
        if rv is not None:
            return url_unquote(rv)

    @property
    def raw_password(self):
        return self._split_auth()[1]

    def to_url(self):
        return url_unparse(self)

    def decode_netloc(self):
        rv = _decode_idna(self.host or '')

        if ':' in rv:
            rv = '[%s]' % rv
        port = self.port
        if port is not None:
            rv = '%s:%d' % (rv, port)
        auth = ':'.join(filter(None, [
            url_unquote(
                self.raw_username or '', errors='strict', unsafe='/:%@'),
            url_unquote(
                self.raw_password or '', errors='strict', unsafe='/:%@'),
        ]))
        if auth:
            rv = '%s@%s' % (auth, rv)
        return rv

    def to_uri_tuple(self):
        return url_parse(iri_to_uri(self).encode('ascii'))

    def to_iri_tuple(self):
        return url_parse(uri_to_iri(self))

    def get_file_location(self, pathformat=None):
        if self.scheme != 'file':
            return None, None

        path = url_unquote(self.path)
        host = self.netloc or None

        if pathformat is None:
            if os.name == 'nt':
                pathformat = 'windows'
            else:
                pathformat = 'posix'

        if pathformat == 'windows':
            if path[:1] == '/' and path[1:2].isalpha() and path[2:3] in '|:':
                path = path[1:2] + ':' + path[3:]
            windows_share = path[:3] in ('\\' * 3, '/' * 3)
            import ntpath
            path = ntpath.normpath(path)
            # Windows shared drives are represented as ``\\host\\directory``.
            # That results in a URL like ``file://///host/directory``, and a
            # path like ``///host/directory``. We need to special-case this
            # because the path contains the hostname.
            if windows_share and host is None:
                parts = path.lstrip('\\').split('\\', 1)
                if len(parts) == 2:
                    host, path = parts
                else:
                    host = parts[0]
                    path = ''
        elif pathformat == 'posix':
            import posixpath
            path = posixpath.normpath(path)
        else:
            raise TypeError('Invalid path format %s' % repr(pathformat))

        if host in ('127.0.0.1', '::1', 'localhost'):
            host = None

        return host, path

    def _split_netloc(self):
        if self._at in self.netloc:
            return self.netloc.split(self._at, 1)
        return None, self.netloc

    def _split_auth(self):
        auth = self._split_netloc()[0]
        if not auth:
            return None, None
        if self._colon not in auth:
            return auth, None
        return auth.split(self._colon, 1)

    def _split_host(self):
        rv = self._split_netloc()[1]
        if not rv:
            return None, None

        if not rv.startswith(self._lbracket):
            if self._colon in rv:
                return rv.split(self._colon, 1)
            return rv, None

        idx = rv.find(self._rbracket)
        if idx < 0:
            return rv, None

        host = rv[1:idx]
        rest = rv[idx + 1:]
        if rest.startswith(self._colon):
            return host, rest[1:]
        return host, None


class URL(BaseURL):
    __slots__ = ()
    _at = '@'
    _colon = ':'
    _lbracket = '['
    _rbracket = ']'

    def __str__(self):
        return self.to_url()

    def encode_netloc(self):
        rv = self.ascii_host or ''
        if ':' in rv:
            rv = '[%s]' % rv
        port = self.port
        if port is not None:
            rv = '%s:%d' % (rv, port)
        auth = ':'.join(filter(None, [
            url_quote(self.raw_username or '', 'utf-8', 'strict', '/:%'),
            url_quote(self.raw_password or '', 'utf-8', 'strict', '/:%'),
        ]))
        if auth:
            rv = '%s@%s' % (auth, rv)
        return to_unicode(rv)

    def encode(self, charset='utf-8', errors='replace'):
        return BytesURL(
            self.scheme.encode('ascii'),
            self.encode_netloc(),
            self.path.encode(charset, errors),
            self.query.encode(charset, errors),
            self.fragment.encode(charset, errors)
        )


class BytesURL(BaseURL):
    __slots__ = ()
    _at = b'@'
    _colon = b':'
    _lbracket = b'['
    _rbracket = b']'

    def __str__(self):
        return self.to_url().decode('utf-8', 'replace')

    def encode_netloc(self):
        return self.netloc

    def decode(self, charset='utf-8', errors='replace'):
        return URL(
            self.scheme.decode('ascii'),
            self.decode_netloc(),
            self.path.decode(charset, errors),
            self.query.decode(charset, errors),
            self.fragment.decode(charset, errors)
        )


def url_quote(string, charset='utf-8', errors='strict', safe='/:', unsafe=''):
    if not isinstance(string, (str, bytes, bytearray)):
        string = str(string)
    if isinstance(string, str):
        string = string.encode(charset, errors)
    if isinstance(safe, str):
        safe = safe.encode(charset, errors)
    if isinstance(unsafe, str):
        unsafe = unsafe.encode(charset, errors)
    safe = frozenset(bytearray(safe) + _always_safe) - \
        frozenset(bytearray(unsafe))
    rv = bytearray()
    for char in bytearray(string):
        if char in safe:
            rv.append(char)
        else:
            rv.extend(('%%%02X' % char).encode('ascii'))
    return to_unicode(bytes(rv))


def _unquote_to_bytes(string, unsafe=''):
    if isinstance(string, str):
        string = string.encode('utf-8')
    if isinstance(unsafe, str):
        unsafe = unsafe.encode('utf-8')
    unsafe = frozenset(bytearray(unsafe))
    bits = iter(string.split(b'%'))
    result = bytearray(next(bits, b''))
    for item in bits:
        try:
            char = _hextobyte[item[:2]]
            if char in unsafe:
                raise KeyError()
            result.append(char)
            result.extend(item[2:])
        except KeyError:
            result.extend(b'%')
            result.extend(item)
    return bytes(result)


def url_unquote(string, charset='utf-8', errors='replace', unsafe=''):
    rv = _unquote_to_bytes(string, unsafe)
    if charset is not None:
        rv = rv.decode(charset, errors)
    return rv


def url_quote_plus(string, charset='utf-8', errors='strict', safe=''):
    return url_quote(
        string, charset, errors, safe + ' ', '+').replace(' ', '+')


def url_unquote_plus(s, charset='utf-8', errors='replace'):
    if isinstance(s, str):
        s = s.replace(u'+', u' ')
    else:
        s = s.replace(b'+', b' ')
    return url_unquote(s, charset, errors)


def url_parse(url, scheme=None, allow_fragments=True):
    #s = make_literal_wrapper(url)
    is_text_based = isinstance(url, str)
    if scheme is None:
        scheme = ''
    netloc = query = fragment = ''
    i = url.find(':')
    if i > 0 and _scheme_re.match(to_unicode(url[:i], errors='replace')):
        # make sure "iri" is not actually a port number (in which case
        # "scheme" is really part of the path)
        rest = url[i + 1:]
        if not rest or any(c not in '0123456789' for c in rest):
            # not a port number
            scheme, url = url[:i].lower(), rest

    if url[:2] == '//':
        delim = len(url)
        for c in '/?#':
            wdelim = url.find(c, 2)
            if wdelim >= 0:
                delim = min(delim, wdelim)
        netloc, url = url[2:delim], url[delim:]
        if ('[' in netloc and ']' not in netloc) or \
           (']' in netloc and '[' not in netloc):
            raise ValueError('Invalid IPv6 URL')

    if allow_fragments and '#' in url:
        url, fragment = url.split('#', 1)
    if '?' in url:
        url, query = url.split('?', 1)

    result_type = is_text_based and URL or BytesURL
    return result_type(scheme, netloc, url, query, fragment)


def url_unparse(components):
    scheme, netloc, path, query, fragment = components
    #    normalize_string_tuple(components)
    #s = make_literal_wrapper(scheme)
    url = ''

    # We generally treat file:///x and file:/x the same which is also
    # what browsers seem to do.  This also allows us to ignore a schema
    # register for netloc utilization or having to differenciate between
    # empty and missing netloc.
    if netloc or (scheme and path.startswith('/')):
        if path and path[:1] != '/':
            path = '/' + path
        url = '//' + (netloc or '') + path
    elif path:
        url += path
    if scheme:
        url = scheme + ':' + url
    if query:
        url = url + '?' + query
    if fragment:
        url = url + '#' + fragment
    return url


def _url_encode_impl(obj, charset, encode_keys, sort, key):
    iterable = sdict()
    for key, values in obj.items():
        if not isinstance(values, list):
            values = [values]
        iterable[key] = values
    if sort:
        iterable = sorted(iterable, key=key)
    for key, values in iterable.items():
        for value in values:
            if value is None:
                continue
            if not isinstance(key, bytes):
                key = str(key).encode(charset)
            if not isinstance(value, bytes):
                value = str(value).encode(charset)
            yield url_quote_plus(key) + '=' + url_quote_plus(value)


def url_encode(obj, charset='utf-8', encode_keys=False, sort=False, key=None,
               separator=b'&'):
    separator = to_unicode(separator, 'ascii')
    return separator.join(
        _url_encode_impl(obj, charset, encode_keys, sort, key))


def uri_to_iri(uri, charset='utf-8', errors='replace'):
    if isinstance(uri, tuple):
        uri = url_unparse(uri)
    uri = url_parse(to_unicode(uri, charset))
    path = url_unquote(uri.path, charset, errors, '%/;?')
    query = url_unquote(uri.query, charset, errors, '%;/?:@&=+,$#')
    fragment = url_unquote(uri.fragment, charset, errors, '%;/?:@&=+,$#')
    return url_unparse((uri.scheme, uri.decode_netloc(),
                        path, query, fragment))


def iri_to_uri(iri, charset='utf-8', errors='strict'):
    if isinstance(iri, tuple):
        iri = url_unparse(iri)
    iri = url_parse(to_unicode(iri, charset, errors))

    netloc = iri.encode_netloc()
    path = url_quote(iri.path, charset, errors, '/:~+%')
    query = url_quote(iri.query, charset, errors, '%&[]:;$*()+,!?*/=')
    fragment = url_quote(iri.fragment, charset, errors, '=%&[]:;$()+,!?*/')

    return to_unicode(url_unparse((iri.scheme, netloc, path, query, fragment)))


def url_fix(s, charset='utf-8'):
    # First step is to switch to unicode processing and to convert
    # backslashes (which are invalid in URLs anyways) to slashes.  This is
    # consistent with what Chrome does.
    s = to_unicode(s, charset, 'replace').replace('\\', '/')

    # For the specific case that we look like a malformed windows URL
    # we want to fix this up manually:
    if (
        s.startswith('file://') and s[7:8].isalpha() and
        s[8:10] in (':/', '|/')
    ):
        s = 'file:///' + s[7:]

    url = url_parse(s)
    path = url_quote(url.path, charset, safe='/%+$!*\'(),')
    qs = url_quote_plus(url.query, charset, safe=':&%=+$!*\'(),')
    anchor = url_quote_plus(url.fragment, charset, safe=':&%=+$!*\'(),')
    return to_unicode(
        url_unparse((url.scheme, url.encode_netloc(), path, qs, anchor)))


def _encode_idna(domain):
    # If we're given bytes, make sure they fit into ASCII
    if not isinstance(domain, str):
        domain.decode('ascii')
        return domain

    # Otherwise check if it's already ascii, then return
    try:
        return domain.encode('ascii')
    except UnicodeError:
        pass

    # Otherwise encode each part separately
    parts = domain.split('.')
    for idx, part in enumerate(parts):
        parts[idx] = part.encode('idna')
    return b'.'.join(parts)


def _decode_idna(domain):
    # If the input is a string try to encode it to ascii to
    # do the idna decoding.  if that fails because of an
    # unicode error, then we already have a decoded idna domain
    if isinstance(domain, str):
        try:
            domain = domain.encode('ascii')
        except UnicodeError:
            return domain

    # Decode each part separately.  If a part fails, try to
    # decode it with ascii and silently ignore errors.  This makes
    # most sense because the idna codec does not have error handling
    parts = domain.split(b'.')
    for idx, part in enumerate(parts):
        try:
            parts[idx] = part.decode('idna')
        except UnicodeError:
            parts[idx] = part.decode('ascii', 'ignore')

    return '.'.join(parts)


def _host_is_trusted(hostname, trusted_list):
    if not hostname:
        return False

    if isinstance(trusted_list, str):
        trusted_list = [trusted_list]

    def _normalize(hostname):
        if ':' in hostname:
            hostname = hostname.rsplit(':', 1)[0]
        return _encode_idna(hostname)

    try:
        hostname = _normalize(hostname)
    except UnicodeError:
        return False
    for ref in trusted_list:
        if ref.startswith('.'):
            ref = ref[1:]
            suffix_match = True
        else:
            suffix_match = False
        try:
            ref = _normalize(ref)
        except UnicodeError:
            return False
        if ref == hostname:
            return True
        if suffix_match and hostname.endswith('.' + ref):
            return True
    return False


def get_host(scope, headers, trusted_hosts=None):
    if 'x-forwarded-host' in headers:
        rv = headers['x-forwarded-host'].split(',', 1)[0].strip()
    elif 'host' in headers:
        rv = headers['host']
    else:
        rv = scope['server'][0]
        if (
            (scope['scheme'], scope['server'][1]) not in
            (('https', '443'), ('http', '80'))
        ):
            rv += ':{}'.format(scope['server'][1])
    return rv
