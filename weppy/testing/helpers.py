# -*- coding: utf-8 -*-
"""
    weppy.testing.helpers
    ---------------------

    Provides helpers for testing suite.

    :copyright: (c) 2014-2017 by Giovanni Barillari

    Several parts of this code comes from Werkzeug.
    :copyright: (c) 2015 by Armin Ronacher.

    :license: BSD, see LICENSE for more details.
"""

import codecs
import mimetypes
import re
import sys
from io import BytesIO
from .._compat import PY2, to_bytes, to_native, string_types, iteritems
from ..datastructures import sdict
from .urls import get_host, uri_to_iri, url_quote

if PY2:
    from cookielib import CookieJar
    from urllib2 import Request as U2Request
else:
    from http.cookiejar import CookieJar
    from urllib.request import Request as U2Request


_quoted_string_re = r'"[^"\\]*(?:\\.[^"\\]*)*"'
_option_header_piece_re = re.compile(
    r';\s*(%s|[^\s;,=]+)\s*(?:=\s*(%s|[^;,]+)?)?\s*' %
    (_quoted_string_re, _quoted_string_re)
)
_option_header_start_mime_type = re.compile(r',\s*([^;,\s]+)([;,]\s*.+)?')


class _TestCookieHeaders(object):

    """A headers adapter for cookielib
    """

    def __init__(self, headers):
        self.headers = headers

    def getheaders(self, name):
        headers = []
        name = name.lower()
        for k, v in self.headers:
            if k.lower() == name:
                headers.append(v)
        return headers

    def get_all(self, name, default=None):
        rv = []
        for k, v in self.headers:
            if k.lower() == name.lower():
                rv.append(v)
        return rv or default or []


class _TestCookieResponse(object):

    """Something that looks like a httplib.HTTPResponse, but is actually just an
    adapter for our test responses to make them available for cookielib.
    """

    def __init__(self, headers):
        self.headers = _TestCookieHeaders(headers)

    def info(self):
        return self.headers


class TestCookieJar(CookieJar):

    """A cookielib.CookieJar modified to inject and read cookie headers from
    and to wsgi environments, and wsgi application responses.
    """

    def inject_wsgi(self, environ):
        """Inject the cookies as client headers into the server's wsgi
        environment.
        """
        cvals = []
        for cookie in self:
            cvals.append('%s=%s' % (cookie.name, cookie.value))
        if cvals:
            environ['HTTP_COOKIE'] = '; '.join(cvals)

    def extract_wsgi(self, environ, headers):
        """Extract the server's set-cookie headers as cookies into the
        cookie jar.
        """
        self.extract_cookies(
            _TestCookieResponse(headers),
            U2Request(get_current_url(environ)),
        )


class Headers(dict):
    def __init__(self, headers=[]):
        super(Headers, self).__init__()
        self._list = []
        for header in headers:
            self._list.append(header)
            self[header[0].lower()] = header[1]

    def __getitem__(self, name):
        return super(Headers, self).__getitem__(name.lower())

    def __setitem__(self, name, value):
        return super(Headers, self).__setitem__(name.lower(), value)

    def __iter__(self):
        return iter(self._list)

    def get(self, name, d=None, type=None):
        rv = super(Headers, self).get(name.lower)
        if rv is None:
            return d
        if type is None:
            return rv
        try:
            rv = type(rv)
        except ValueError:
            pass
        return rv

    def to_wsgi_list(self):
        if PY2:
            return [(to_native(k), v.encode('latin1')) for k, v in self]
        return list(self)


class _FileHandler(object):
    def __init__(self, stream=None, filename=None, name=None,
                 content_type=None, content_length=None,
                 headers=None):
        self.name = name
        self.stream = stream or BytesIO()

        # if no filename is provided we can attempt to get the filename
        # from the stream object passed.  There we have to be careful to
        # skip things like <fdopen>, <stderr> etc.  Python marks these
        # special filenames with angular brackets.
        if filename is None:
            filename = getattr(stream, 'name', None)
            #s = make_literal_wrapper(filename)
            if filename and filename[0] == '<' and filename[-1] == '>':
                filename = None

            # On Python 3 we want to make sure the filename is always unicode.
            # This might not be if the name attribute is bytes due to the
            # file being opened from the bytes API.
            if not PY2 and isinstance(filename, bytes):
                filename = filename.decode(get_filesystem_encoding(),
                                           'replace')

        self.filename = filename
        if headers is None:
            headers = Headers()
        self.headers = headers
        if content_type is not None:
            headers['Content-Type'] = content_type
        if content_length is not None:
            headers['Content-Length'] = str(content_length)

    def _parse_content_type(self):
        if not hasattr(self, '_parsed_content_type'):
            self._parsed_content_type = \
                parse_options_header(self.content_type)

    @property
    def content_type(self):
        return self.headers.get('content-type')

    @property
    def content_length(self):
        return int(self.headers.get('content-length') or 0)

    @property
    def mimetype(self):
        self._parse_content_type()
        return self._parsed_content_type[0].lower()

    @property
    def mimetype_params(self):
        self._parse_content_type()
        return self._parsed_content_type[1]

    def save(self, dst, buffer_size=16384):
        """Save the file to a destination path or file object.  If the
        destination is a file object you have to close it yourself after the
        call.  The buffer size is the number of bytes held in memory during
        the copy process.  It defaults to 16KB.
        For secure file saving also have a look at :func:`secure_filename`.
        :param dst: a filename or open file object the uploaded file
                    is saved to.
        :param buffer_size: the size of the buffer.  This works the same as
                            the `length` parameter of
                            :func:`shutil.copyfileobj`.
        """
        from shutil import copyfileobj
        close_dst = False
        if isinstance(dst, string_types):
            dst = open(dst, 'wb')
            close_dst = True
        try:
            copyfileobj(self.stream, dst, buffer_size)
        finally:
            if close_dst:
                dst.close()

    def close(self):
        """Close the underlying file if possible."""
        try:
            self.stream.close()
        except Exception:
            pass

    def __nonzero__(self):
        return bool(self.filename)
    __bool__ = __nonzero__

    def __getattr__(self, name):
        return getattr(self.stream, name)

    def __iter__(self):
        return iter(self.readline, '')

    def __repr__(self):
        return '<%s: %r (%r)>' % (
            self.__class__.__name__,
            self.filename,
            self.content_type
        )


class filesdict(sdict):
    def add_file(self, name, file, filename=None, content_type=None):
        if isinstance(file, _FileHandler):
            value = file
        else:
            if isinstance(file, string_types):
                if filename is None:
                    filename = file
                file = open(file, 'rb')
            if filename and content_type is None:
                content_type = mimetypes.guess_type(filename)[0] or \
                    'application/octet-stream'
            value = _FileHandler(file, filename, name, content_type)
        self[name] = value


def _get_query_string(environ):
    qs = to_bytes(environ.get('QUERY_STRING', ''))
    return to_native(url_quote(qs, safe=':&%=+$!*\'(),'))


def get_current_url(environ, root_only=False, strip_querystring=False,
                    host_only=False, trusted_hosts=None):
    tmp = [environ['wsgi.url_scheme'], '://', get_host(environ, trusted_hosts)]
    cat = tmp.append
    if host_only:
        return uri_to_iri(''.join(tmp) + '/')
    cat(url_quote(to_bytes(environ.get('SCRIPT_NAME', ''))).rstrip('/'))
    cat('/')
    if not root_only:
        cat(url_quote(to_bytes(environ.get('PATH_INFO', '')).lstrip(b'/')))
        if not strip_querystring:
            qs = _get_query_string(environ)
            if qs:
                cat('?' + qs)
    return uri_to_iri(''.join(tmp))


def _is_ascii_encoding(encoding):
    if encoding is None:
        return False
    try:
        return codecs.lookup(encoding).name == 'ascii'
    except LookupError:
        return False


def get_filesystem_encoding():
    rv = sys.getfilesystemencoding()
    if (sys.platform.startswith('linux') or 'bsd' in sys.platform) and not rv \
       or _is_ascii_encoding(rv):
        return 'utf-8'
    return rv


def unquote_header_value(value, is_filename=False):
    if value and value[0] == value[-1] == '"':
        # this is not the real unquoting, but fixing this so that the
        # RFC is met will result in bugs with internet explorer and
        # probably some other browsers as well.  IE for example is
        # uploading files with "C:\foo\bar.txt" as filename
        value = value[1:-1]

        # if this is a filename and the starting characters look like
        # a UNC path, then just return the value without quotes.  Using the
        # replace sequence below on a UNC path has the effect of turning
        # the leading double slash into a single slash and then
        # _fix_ie_filename() doesn't work correctly.  See #458.
        if not is_filename or value[:2] != '\\\\':
            return value.replace('\\\\', '\\').replace('\\"', '"')
    return value


def parse_options_header(value, multiple=False):
    if not value:
        return '', {}
    result = []
    value = "," + value.replace("\n", ",")
    while value:
        match = _option_header_start_mime_type.match(value)
        if not match:
            break
        result.append(match.group(1))  # mimetype
        options = {}
        # Parse options
        rest = match.group(2)
        while rest:
            optmatch = _option_header_piece_re.match(rest)
            if not optmatch:
                break
            option, option_value = optmatch.groups()
            option = unquote_header_value(option)
            if option_value is not None:
                option_value = unquote_header_value(
                    option_value,
                    option == 'filename')
            options[option] = option_value
            rest = rest[optmatch.end():]
        result.append(options)
        if multiple is False:
            return tuple(result)
        value = rest

    return tuple(result)


def stream_encode_multipart(values, threshold=1024 * 500, boundary=None,
                            charset='utf-8'):
    """Encode a dict of values (either strings or file descriptors or
    :class:`FileStorage` objects.) into a multipart encoded string stored
    in a file descriptor.
    """
    if boundary is None:
        from time import time
        from random import random
        boundary = '---------------WeppyFormPart_%s%s' % (time(), random())
    _closure = [BytesIO(), 0, False]

    write_binary = _closure[0].write

    def write(string):
        write_binary(string.encode(charset))

    for key, values in iteritems(values):
        if not isinstance(values, list):
            values = [values]
        for value in values:
            write('--%s\r\nContent-Disposition: form-data; name="%s"' %
                  (boundary, key))
            reader = getattr(value, 'read', None)
            if reader is not None:
                filename = getattr(value, 'filename',
                                   getattr(value, 'name', None))
                content_type = getattr(value, 'content_type', None)
                if content_type is None:
                    content_type = filename and \
                        mimetypes.guess_type(filename)[0] or \
                        'application/octet-stream'
                if filename is not None:
                    write('; filename="%s"\r\n' % filename)
                else:
                    write('\r\n')
                write('Content-Type: %s\r\n\r\n' % content_type)
                while 1:
                    chunk = reader(16384)
                    if not chunk:
                        break
                    write_binary(chunk)
            else:
                if not isinstance(value, string_types):
                    value = str(value)
                else:
                    value = to_bytes(value, charset)
                write('\r\n\r\n')
                write_binary(value)
            write('\r\n')
    write('--%s--\r\n' % boundary)

    length = int(_closure[0].tell())
    _closure[0].seek(0)
    return _closure[0], length, boundary
