# -*- coding: utf-8 -*-
"""
    weppy.testing.env
    -----------------

    Provides environment class for testing suite.

    :copyright: (c) 2014-2017 by Giovanni Barillari

    Several parts of this code comes from Werkzeug.
    :copyright: (c) 2015 by Armin Ronacher.

    :license: BSD, see LICENSE for more details.
"""

import cgi
import sys
from datetime import datetime
from io import BytesIO
from .._compat import text_type, iteritems, itervalues
from ..datastructures import sdict
from .helpers import Headers, filesdict, stream_encode_multipart
from .urls import iri_to_uri, url_fix, url_parse, url_unparse, url_encode


class EnvironBuilder(object):
    #: This class creates a WSGI environment for testing purposes.

    #: the server protocol to use.  defaults to HTTP/1.1
    server_protocol = 'HTTP/1.1'

    #: the wsgi version to use.  defaults to (1, 0)
    wsgi_version = (1, 0)

    def __init__(self, path='/', base_url=None, query_string=None,
                 method='GET', input_stream=None, content_type=None,
                 content_length=None, errors_stream=None, headers=None,
                 data=None, environ_base=None, environ_overrides=None,
                 charset='utf-8'):
        #path_s = make_literal_wrapper(path)
        # if query_string is None and path_s('?') in path:
        #     path, query_string = path.split(path_s('?'), 1)
        if query_string is None and '?' in path:
            path, query_string = path.split('?', 1)
        self.charset = charset
        self.path = iri_to_uri(path)
        if base_url is not None:
            base_url = url_fix(iri_to_uri(base_url, charset), charset)
        self.base_url = base_url
        if isinstance(query_string, (bytes, text_type)):
            self.query_string = query_string
        else:
            if query_string is None:
                query_string = sdict()
            elif not isinstance(query_string, sdict):
                query_string = self._parse_querystring(query_string)
            self.args = query_string
        self.method = method
        if headers is None:
            headers = Headers()
        elif not isinstance(headers, Headers):
            headers = Headers(headers)
        self.headers = headers
        if content_type is not None:
            self.content_type = content_type
        if errors_stream is None:
            errors_stream = sys.stderr
        self.errors_stream = errors_stream
        self.environ_base = environ_base
        self.environ_overrides = environ_overrides
        self.input_stream = input_stream
        self.content_length = content_length
        self.closed = False

        if data:
            if input_stream is not None:
                raise TypeError('can\'t provide input stream and data')
            if isinstance(data, text_type):
                data = data.encode(self.charset)
            if isinstance(data, bytes):
                self.input_stream = BytesIO(data)
                if self.content_length is None:
                    self.content_length = len(data)
            else:
                for key, values in iteritems(data):
                    if not isinstance(values, list):
                        values = [values]
                    for v in values:
                        if isinstance(v, (tuple)) or hasattr(v, 'read'):
                            self._add_file_from_data(key, v)
                        else:
                            if self.form[key] is None:
                                self.form[key] = []
                            self.form[key].append(v)

    @staticmethod
    def _parse_querystring(query_string):
        dget = cgi.parse_qs(query_string, keep_blank_values=1)
        params = sdict(dget)
        for key, value in iteritems(params):
            if isinstance(value, list) and len(value) == 1:
                params[key] = value[0]
        return params

    def _add_file_from_data(self, key, value):
        """Called in the EnvironBuilder to add files from the data dict."""
        if isinstance(value, tuple):
            self.files.add_file(key, *value)
        else:
            self.files.add_file(key, value)

    def _get_base_url(self):
        return url_unparse((self.url_scheme, self.host,
                            self.script_root, '', '')).rstrip('/') + '/'

    def _set_base_url(self, value):
        if value is None:
            scheme = 'http'
            netloc = 'localhost'
            script_root = ''
        else:
            scheme, netloc, script_root, qs, anchor = url_parse(value)
            if qs or anchor:
                raise ValueError('base url must not contain a query string '
                                 'or fragment')
        self.script_root = script_root.rstrip('/')
        self.host = netloc
        self.url_scheme = scheme

    base_url = property(_get_base_url, _set_base_url)
    del _get_base_url, _set_base_url

    def _get_content_type(self):
        ct = self.headers.get('Content-Type')
        if ct is None and not self._input_stream:
            if self._files:
                return 'multipart/form-data'
            elif self._form:
                return 'application/x-www-form-urlencoded'
            return None
        return ct

    def _set_content_type(self, value):
        if value is None:
            self.headers.pop('Content-Type', None)
        else:
            self.headers['Content-Type'] = value

    content_type = property(_get_content_type, _set_content_type)
    del _get_content_type, _set_content_type

    def _get_content_length(self):
        return self.headers.get('Content-Length', type=int)

    def _set_content_length(self, value):
        if value is None:
            self.headers.pop('Content-Length', None)
        else:
            self.headers['Content-Length'] = str(value)

    content_length = property(_get_content_length, _set_content_length)
    del _get_content_length, _set_content_length

    def form_property(name, storage):
        key = '_' + name

        def getter(self):
            if self._input_stream is not None:
                raise AttributeError('an input stream is defined')
            rv = getattr(self, key)
            if rv is None:
                rv = storage()
                setattr(self, key, rv)

            return rv

        def setter(self, value):
            self._input_stream = None
            setattr(self, key, value)
        return property(getter, setter)

    form = form_property('form', sdict)
    files = form_property('files', filesdict)
    del form_property

    def _get_input_stream(self):
        return self._input_stream

    def _set_input_stream(self, value):
        self._input_stream = value
        self._form = self._files = None

    input_stream = property(_get_input_stream, _set_input_stream, doc='''
        An optional input stream.  If you set this it will clear
        :attr:`form` and :attr:`files`.''')
    del _get_input_stream, _set_input_stream

    def _get_query_string(self):
        if self._query_string is None:
            if self._args is not None:
                return url_encode(self._args, charset=self.charset)
            return ''
        return self._query_string

    def _set_query_string(self, value):
        self._query_string = value
        self._args = None

    query_string = property(_get_query_string, _set_query_string)
    del _get_query_string, _set_query_string

    def _get_args(self):
        if self._query_string is not None:
            raise AttributeError('a query string is defined')
        if self._args is None:
            self._args = sdict()
        return self._args

    def _set_args(self, value):
        self._query_string = None
        self._args = value

    args = property(_get_args, _set_args)
    del _get_args, _set_args

    @property
    def server_name(self):
        """The server name (read-only, use :attr:`host` to set)"""
        return self.host.split(':', 1)[0]

    @property
    def server_port(self):
        """The server port as integer (read-only, use :attr:`host` to set)"""
        pieces = self.host.split(':', 1)
        if len(pieces) == 2 and pieces[1].isdigit():
            return int(pieces[1])
        elif self.url_scheme == 'https':
            return 443
        return 80

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    def close(self):
        """Closes all files.  If you put real :class:`file` objects into the
        :attr:`files` dict you can call this method to automatically close
        them all in one go.
        """
        if self.closed:
            return
        try:
            files = itervalues(self.files)
        except AttributeError:
            files = ()
        for f in files:
            try:
                f.close()
            except Exception:
                pass
        self.closed = True

    def get_environ(self):
        """Return the built environ."""
        input_stream = self.input_stream
        content_length = self.content_length
        content_type = self.content_type

        if input_stream is not None:
            start_pos = input_stream.tell()
            input_stream.seek(0, 2)
            end_pos = input_stream.tell()
            input_stream.seek(start_pos)
            content_length = end_pos - start_pos
        elif content_type == 'multipart/form-data':
            values = sdict()
            for d in [self.files, self.form]:
                for key, val in iteritems(d):
                    values[key] = val
            input_stream, content_length, boundary = \
                stream_encode_multipart(values, charset=self.charset)
            content_type += '; boundary="%s"' % boundary
        elif content_type == 'application/x-www-form-urlencoded':
            values = url_encode(self.form, charset=self.charset)
            values = values.encode('ascii')
            content_length = len(values)
            input_stream = BytesIO(values)
        else:
            input_stream = BytesIO()

        result = {}
        if self.environ_base:
            result.update(self.environ_base)

        # def _path_encode(x):
        #     return to_bytes(url_unquote(x, self.charset), self.charset)

        # qs = to_bytes(self.query_string)

        result.update({
            'REQUEST_METHOD': self.method,
            #'SCRIPT_NAME': _path_encode(self.script_root),
            #'PATH_INFO': _path_encode(self.path),
            #'QUERY_STRING': qs,
            'SCRIPT_NAME': self.script_root,
            'PATH_INFO': self.path,
            'QUERY_STRING': self.query_string,
            'SERVER_NAME': self.server_name,
            'SERVER_PORT': str(self.server_port),
            'HTTP_HOST': self.host,
            'SERVER_PROTOCOL': self.server_protocol,
            'CONTENT_TYPE': content_type or '',
            'CONTENT_LENGTH': str(content_length or '0'),
            'wsgi.version': self.wsgi_version,
            'wsgi.url_scheme': self.url_scheme,
            'wsgi.input': input_stream,
            'wsgi.errors': self.errors_stream,
            'wpp.application': 'test_application_name',
            'wpp.now': datetime.utcnow()
        })
        for key, value in self.headers.to_wsgi_list():
            result['HTTP_%s' % key.upper().replace('-', '_')] = value
        if self.environ_overrides:
            result.update(self.environ_overrides)
        return result
