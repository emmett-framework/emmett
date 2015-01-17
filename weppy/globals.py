# -*- coding: utf-8 -*-
"""
    weppy.globals
    -------------

    Provide the current object. Used by application to deal with
    request, response, session (if loaded with handlers).

    :copyright: (c) 2015 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

import cgi
import copy
import json
import threading

from ._compat import SimpleCookie
from ._internal import ObjectProxy, LimitedStream
from .datastructures import sdict
from .helpers import get_flashed_messages
from .tags import xmlescape
from .libs.contenttype import contenttype


class Request(object):
    def __init__(self, environ):
        self.environ = environ
        self.scheme = 'https' if \
            environ.get('wsgi.url_scheme', '').lower() == 'https' or \
            environ.get('HTTP_X_FORWARDED_PROTO', '').lower() == 'https' or \
            environ.get('HTTPS', '') == 'on' else 'http'
        self.name = '<module>.<func>'
        self.hostname = environ['HTTP_HOST']
        self.method = environ.get('REQUEST_METHOD', 'GET').lower()
        self.path_info = environ['PATH_INFO']
        self.input = environ.get('wsgi.input')
        self._now_ref = environ['wpp.appnow']
        self.nowutc = environ['wpp.now.utc']
        self.nowloc = environ['wpp.now.local']
        self.application = environ['wpp.application']

    def _parse_get_vars(self):
        query_string = self.environ.get('QUERY_STRING', '')
        dget = cgi.parse_qs(query_string, keep_blank_values=1)
        get_vars = self._get_vars = sdict(dget)
        for (key, value) in get_vars.iteritems():
            if isinstance(value, list) and len(value) == 1:
                get_vars[key] = value[0]

    def __parse_post_json(self):
        content_length = self.environ.get('CONTENT_LENGTH')
        try:
            content_length = max(0, int(content_length))
        except:
            content_length = None
        if content_length is None:
            return {}
        try:
            json_vars = json.load(LimitedStream(self.input, content_length))
        except:
            json_vars = {}
        return json_vars

    def _parse_post_vars(self):
        environ = self.environ
        post_vars = self._post_vars = sdict()
        if self.environ.get('CONTENT_TYPE', '')[:16] == 'application/json':
            json_vars = self.__parse_post_json()
            post_vars.update(json_vars)
            return
        if self.input and environ.get('REQUEST_METHOD') in ('POST', 'PUT', 'DELETE', 'BOTH'):
            dpost = cgi.FieldStorage(fp=self.input, environ=environ,
                                     keep_blank_values=1)
            try:
                keys = sorted(dpost)
            except:
                keys = []
            for key in keys:
                dpk = dpost[key]
                if not isinstance(dpk, list):
                    dpk = [dpk]
                dpk = [item.value if not item.filename else item for item in dpk]
                post_vars[key] = dpk
            for (key, value) in self._post_vars.iteritems():
                if isinstance(value, list) and len(value) == 1:
                    post_vars[key] = value[0]

    def _parse_all_vars(self):
        self._vars = copy.copy(self.get_vars)
        for key, value in self.post_vars.iteritems():
            if not key in self._vars:
                self._vars[key] = value
            else:
                if not isinstance(self._vars[key], list):
                    self._vars[key] = [self._vars[key]]
                self._vars[key] += value if isinstance(value, list) else [value]

    def _parse_client(self):
        import re
        regex_client = re.compile('[\w\-:]+(\.[\w\-]+)*\.?')
        g = regex_client.search(self.environ.get('HTTP_X_FORWARDED_FOR', ''))
        client = (g.group() or '').split(',')[0] if g else None
        if client in (None, '', 'unknown'):
            g = regex_client.search(self.environ.get('REMOTE_ADDR', ''))
            if g:
                client = g.group()
            elif self.hostname.startswith('['):  # IPv6
                client = '::1'
            else:
                client = '127.0.0.1'  # IPv4
        self._client = client

    @property
    def now(self):
        if self._now_ref == "utc":
            return self.nowutc
        return self.nowloc

    @property
    def get_vars(self):
        " lazily parse the query string into get_vars "
        if not hasattr(self, '_get_vars'):
            self._parse_get_vars()
        return self._get_vars

    @property
    def post_vars(self):
        " lazily parse the request body into post_vars "
        if not hasattr(self, '_post_vars'):
            self._parse_post_vars()
        return self._post_vars

    @property
    def vars(self):
        " lazily parse the request body into post_vars "
        if not hasattr(self, '_vars'):
            self._parse_all_vars()
        return self._vars

    @property
    def env(self):
        """
        lazily parse the environment variables into a storage,
        for backward compatibility, it is slow
        """
        if not hasattr(self, '_env'):
            self._env = sdict((k.lower().replace('.', '_'), v)
                                for (k, v) in self.environ.iteritems())
        return self._env

    @property
    def cookies(self):
        " lazily parse the request cookies "
        if not hasattr(self, '_request_cookies'):
            self._cookies = SimpleCookie()
            self._cookies.load(self.environ.get('HTTP_COOKIE', ''))
        return self._cookies

    @property
    def client(self):
        if not hasattr(self, '_client'):
            self._parse_client()
        return self._client

    @property
    def isajax(self):
        return self.environ.get('HTTP_X_REQUESTED_WITH', '').lower == \
            'xmlhttprequest'

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
            '<meta name="%s" content="%s" />\n' % (k, xmlescape(v))
            for k, v in (self.meta or {}).iteritems())
        s += '\n'.join(
            '<meta property="%s" content="%s" />\n' % (k, xmlescape(v))
            for k, v in (self.meta_prop or {}).iteritems())
        return s

    __getitem__ = object.__getattribute__
    __setitem__ = object.__setattr__


class Current(threading.local):

    def initialize(self, environ):
        self.__dict__.clear()
        self.environ = environ
        self.request = Request(environ)
        self.response = Response(environ)
        self.session = None
        self._language = environ.get('HTTP_ACCEPT_LANGUAGE')

    ## keep this for templates?
    @property
    def T(self):
        " lazily allocate the T object "
        if not hasattr(self, '_t'):
            from .language import T
            self._t = T
        return self._t


current = Current()

request = ObjectProxy(current, "request")
response = ObjectProxy(current, "response")
session = ObjectProxy(current, "session")
