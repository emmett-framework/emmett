# -*- coding: utf-8 -*-
"""
    weppy.globals
    -------------

    Provide the current object. Used by application to deal with
    request, response, session (if loaded with handlers).

    :copyright: (c) 2014-2016 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

import cgi
import copy
import json
import re
import threading

from ._compat import SimpleCookie, iteritems, to_native
from ._internal import ObjectProxy, LimitedStream
from .datastructures import sdict
from .helpers import get_flashed_messages
from .tags import htmlescape
from .utils import cachedprop
from .libs.contenttype import contenttype


_regex_client = re.compile('[\w\-:]+(\.[\w\-]+)*\.?')


class Request(object):
    def __init__(self, environ):
        self.environ = environ
        self.scheme = 'https' if \
            environ.get('wsgi.url_scheme', '').lower() == 'https' or \
            environ.get('HTTP_X_FORWARDED_PROTO', '').lower() == 'https' or \
            environ.get('HTTPS', '') == 'on' else 'http'
        self.name = '<module>.<func>'
        self.hostname = environ.get('HTTP_HOST') or '%s:%s' % \
            (environ.get('SERVER_NAME', ''), environ.get('SERVER_PORT', ''))
        self.method = environ.get('REQUEST_METHOD', 'GET').lower()
        self.path_info = environ.get('PATH_INFO') or \
            environ.get('REQUEST_URI').split('?')[0]
        self.input = environ.get('wsgi.input')
        self._now_ref = environ['wpp.appnow']
        self.nowutc = environ['wpp.now.utc']
        self.nowloc = environ['wpp.now.local']
        self.application = environ['wpp.application']

    @cachedprop
    def now(self):
        if self._now_ref == "utc":
            return self.nowutc
        return self.nowloc

    @cachedprop
    def query_params(self):
        query_string = self.environ.get('QUERY_STRING', '')
        dget = cgi.parse_qs(query_string, keep_blank_values=1)
        params = sdict(dget)
        for key, value in iteritems(params):
            if isinstance(value, list) and len(value) == 1:
                params[key] = value[0]
        return params

    def __parse_json_params(self):
        content_length = self.environ.get('CONTENT_LENGTH')
        try:
            content_length = max(0, int(content_length))
        except:
            content_length = None
        if content_length is None:
            return {}
        try:
            stream = LimitedStream(self.input, content_length)
            params = json.loads(to_native(stream.read()))
        except:
            params = {}
        return params

    @cachedprop
    def body_params(self):
        params = sdict()
        if self.environ.get('CONTENT_TYPE', '')[:16] == 'application/json':
            json_params = self.__parse_json_params()
            params.update(json_params)
            return params
        if self.input and self.environ.get('REQUEST_METHOD') in \
                ('POST', 'PUT', 'DELETE', 'BOTH'):
            dpost = cgi.FieldStorage(fp=self.input, environ=self.environ,
                                     keep_blank_values=1)
            try:
                keys = sorted(dpost)
            except:
                keys = []
            for key in keys:
                dpk = dpost[key]
                if not isinstance(dpk, list):
                    dpk = [dpk]
                dpk = [item.value if not item.filename else item
                       for item in dpk]
                params[key] = dpk
            for key, value in list(params.items()):
                if isinstance(value, list) and len(value) == 1:
                    params[key] = value[0]
        return params

    @cachedprop
    def params(self):
        rv = copy.copy(self.query_params)
        for key, val in iteritems(self.body_params):
            if key not in rv:
                rv[key] = val
            else:
                if not isinstance(rv[key], list):
                    rv[key] = [rv[key]]
                rv[key] += val if isinstance(val, list) else [val]
        return rv

    @cachedprop
    def cookies(self):
        cookies = SimpleCookie()
        for cookie in self.environ.get('HTTP_COOKIE', '').split(';'):
            cookies.load(cookie)
        return cookies

    @cachedprop
    def client(self):
        g = _regex_client.search(self.environ.get('HTTP_X_FORWARDED_FOR', ''))
        client = (g.group() or '').split(',')[0] if g else None
        if client in (None, '', 'unknown'):
            g = _regex_client.search(self.environ.get('REMOTE_ADDR', ''))
            if g:
                client = g.group()
            elif self.hostname.startswith('['):
                # IPv6
                client = '::1'
            else:
                # IPv4
                client = '127.0.0.1'
        return client

    @cachedprop
    def isajax(self):
        return self.environ.get('HTTP_X_REQUESTED_WITH', '').lower == \
            'xmlhttprequest'

    @cachedprop
    def env(self):
        #: parse the environment variables into a sdict
        _env = sdict(
            (k.lower().replace('.', '_'), v)
            for k, v in iteritems(self.environ)
        )
        return _env

    __getitem__ = object.__getattribute__
    __setitem__ = object.__setattr__


class Response(object):
    def __init__(self, environ):
        self.status = 200
        self.cookies = SimpleCookie()
        self.headers = {'Content-Type':
                        contenttype(environ['PATH_INFO'], 'text/html')}
        self.meta = sdict()
        self.meta_prop = sdict()

    def alerts(self, **kwargs):
        return get_flashed_messages(**kwargs)

    def get_meta(self):
        s = '\n'.join(
            '<meta name="%s" content="%s" />\n' % (k, htmlescape(v))
            for k, v in iteritems(self.meta or {}))
        s += '\n'.join(
            '<meta property="%s" content="%s" />\n' % (k, htmlescape(v))
            for k, v in iteritems(self.meta_prop or {}))
        return s

    __getitem__ = object.__getattribute__
    __setitem__ = object.__setattr__


class Current(threading.local):
    _language = None

    def initialize(self, environ):
        self.__dict__.clear()
        self.environ = environ
        self.request = Request(environ)
        self.response = Response(environ)
        self.session = None
        self._language = environ.get('HTTP_ACCEPT_LANGUAGE')

    @cachedprop
    def T(self):
        from .language import T
        return T


current = Current()

request = ObjectProxy(current, "request")
response = ObjectProxy(current, "response")
session = ObjectProxy(current, "session")
