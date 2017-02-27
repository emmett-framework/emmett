# -*- coding: utf-8 -*-
"""
    weppy.globals
    -------------

    Provide the current object. Used by application to deal with
    request, response, session (if loaded with pipeline).

    :copyright: (c) 2014-2017 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

import cgi
import copy
import json
import pendulum
import re
import threading
from datetime import datetime
from ._compat import SimpleCookie, iteritems, to_native
from ._internal import ObjectProxy, LimitedStream
from .datastructures import sdict, Accept, EnvironHeaders
from .helpers import get_flashed_messages
from .language import T, _instance as _translator_instance
from .language.helpers import LanguageAccept
from .html import htmlescape
from .utils import cachedprop
from .libs.contenttype import contenttype


_regex_client = re.compile('[\w\-:]+(\.[\w\-]+)*\.?')
_regex_accept = re.compile(r'''
    ([^\s;,]+(?:[ \t]*;[ \t]*(?:[^\s;,q][^\s;,]*|q[^\s;,=][^\s;,]*))*)
    (?:[ \t]*;[ \t]*q=(\d*(?:\.\d+)?)[^,]*)?''', re.VERBOSE)


class Request(object):
    def __init__(self, environ):
        self.name = None
        self.environ = environ
        self.scheme = environ['wsgi.url_scheme']
        self.hostname = self._get_hostname_(environ)
        self.method = environ['REQUEST_METHOD']
        self.path_info = environ['PATH_INFO'] or '/'

    @staticmethod
    def _get_hostname_(environ):
        try:
            host = environ['HTTP_HOST']
        except KeyError:
            host = environ['SERVER_NAME']
        return host

    @property
    def appname(self):
        return self.environ['wpp.application']

    @cachedprop
    def input(self):
        return self.environ.get('wsgi.input')

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
            params = json.loads(to_native(stream.read())) or {}
        except:
            params = {}
        return params

    def __parse_accept_header(self, value, cls=None):
        if cls is None:
            cls = Accept
        if not value:
            return cls(None)
        result = []
        for match in _regex_accept.finditer(value):
            quality = match.group(2)
            if not quality:
                quality = 1
            else:
                quality = max(min(float(quality), 1), 0)
            result.append((match.group(1), quality))
        return cls(result)

    @cachedprop
    def now(self):
        return pendulum.instance(self.environ['wpp.now'], 'UTC')

    @cachedprop
    def now_local(self):
        return self.now.in_timezone(pendulum.local_timezone())

    @cachedprop
    def query_params(self):
        query_string = self.environ.get('QUERY_STRING', '')
        dget = cgi.parse_qs(query_string, keep_blank_values=1)
        params = sdict(dget)
        for key, value in iteritems(params):
            if isinstance(value, list) and len(value) == 1:
                params[key] = value[0]
        return params

    @cachedprop
    def body_params(self):
        params = sdict()
        if self.environ.get('CONTENT_TYPE', '')[:16] == 'application/json':
            json_params = self.__parse_json_params()
            params.update(json_params)
            return params
        if self.input and self.method in ('POST', 'PUT', 'DELETE', 'BOTH'):
            try:
                dpost = cgi.FieldStorage(
                    fp=self.input, environ=self.environ, keep_blank_values=1)
                keys = sorted(dpost)
            except:
                keys = []
            for key in keys:
                dpk = dpost[key]
                if not isinstance(dpk, list):
                    dpk = [dpk]
                dpk = [
                    item.value if not item.filename else item for item in dpk]
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
    def headers(self):
        return EnvironHeaders(self.environ)

    @cachedprop
    def cookies(self):
        cookies = SimpleCookie()
        for cookie in self.environ.get('HTTP_COOKIE', '').split(';'):
            cookies.load(cookie)
        return cookies

    @cachedprop
    def accept_languages(self):
        return self.__parse_accept_header(
            self.environ.get('HTTP_ACCEPT_LANGUAGE'), LanguageAccept)

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
        return sdict(
            (k.lower().replace('.', '_'), v)
            for k, v in iteritems(self.environ)
        )

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
    def __init__(self, *args, **kwargs):
        self._get_lang = self._empty_lang
        self._get_now = self._sys_now

    def initialize(self, environ):
        self.__dict__.clear()
        self.environ = environ
        self.request = Request(environ)
        self.response = Response(environ)
        self.session = None
        self._get_lang = self._req_lang
        self._get_now = self._req_now

    @property
    def T(self):
        return T

    def _empty_lang(self):
        return None

    def _req_lang(self):
        return self.request.accept_languages.best_match(
            list(_translator_instance._t.all_languages))

    @cachedprop
    def language(self):
        return self._get_lang()

    def _sys_now(self):
        return pendulum.instance(datetime.utcnow(), 'UTC')

    def _req_now(self):
        return self.request.now

    @property
    def now(self):
        return self._get_now()


current = Current()

request = ObjectProxy(current, "request")
response = ObjectProxy(current, "response")
session = ObjectProxy(current, "session")


def now():
    return current._get_now()
