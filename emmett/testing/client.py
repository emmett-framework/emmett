# -*- coding: utf-8 -*-
"""
    emmett.testing.client
    ---------------------

    Provides base classes for testing suite.

    :copyright: 2014 Giovanni Barillari

    Several parts of this code comes from Werkzeug.
    :copyright: (c) 2015 by Armin Ronacher.

    :license: BSD-3-Clause
"""

import asyncio
import copy
import types

from io import BytesIO

from ..asgi.handlers import HTTPHandler
from ..asgi.wrappers import Request
from ..ctx import RequestContext, current
from ..http import HTTP, HTTPResponse
from ..wrappers.response import Response
from ..utils import cachedprop
from .env import ScopeBuilder
from .helpers import TestCookieJar, Headers
from .urls import get_host, url_parse, url_unparse


class ClientContextResponse(Response):
    def __init__(self, original_response: Response):
        super().__init__()
        self.status = original_response.status
        self.headers._data.update(original_response.headers._data)
        self.cookies.update(original_response.cookies.copy())
        self.__dict__.update(original_response.__dict__)


class ClientContext:
    def __init__(self, ctx):
        self.request = Request(ctx.request._scope, None, None)
        self.response = ClientContextResponse(ctx.response)
        self.session = copy.deepcopy(ctx.session)
        self.T = current.T

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, tb):
        pass


class ClientHTTPHandler(HTTPHandler):
    async def dynamic_handler(self, scope, receive, send):
        request = Request(
            scope,
            receive,
            send,
            max_content_length=self.app.config.request_max_content_length,
            body_timeout=self.app.config.request_body_timeout
        )
        response = Response()
        ctx = RequestContext(self.app, request, response)
        ctx_token = current._init_(ctx)
        try:
            http = await self.router.dispatch(request, response)
        except HTTPResponse as http_exception:
            http = http_exception
            #: render error with handlers if in app
            error_handler = self.app.error_handlers.get(http.status_code)
            if error_handler:
                http = HTTP(
                    http.status_code,
                    await error_handler(),
                    headers=response.headers,
                    cookies=response.cookies
                )
        except Exception:
            self.app.log.exception('Application exception:')
            http = HTTP(
                500,
                await self.error_handler(),
                headers=response.headers
            )
        finally:
            scope['emt.ctx'] = ClientContext(ctx)
            current._close_(ctx_token)
        return http


class ClientResponse(object):
    def __init__(self, ctx, raw, status, headers):
        self.context = ctx
        self.raw = raw
        self.status = status
        self.headers = headers
        self._close = lambda: None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, tb):
        pass

    @cachedprop
    def data(self):
        self._ensure_sequence()
        rv = b''.join(self.iter_encoded())
        return rv.decode('utf8')

    @property
    def is_sequence(self):
        return isinstance(self.raw, (tuple, list))

    def _ensure_sequence(self, mutable=False):
        if self.is_sequence:
            # if we need a mutable object, we ensure it's a list.
            if mutable and not isinstance(self.response, list):
                self.response = list(self.response)
            return
        self.make_sequence()

    def make_sequence(self):
        if not self.is_sequence:
            close = getattr(self.raw, 'close', None)
            self.raw = list(self.iter_encoded())
            self._close = close

    def close(self):
        if hasattr(self.raw, 'close'):
            self.response.close()
        self._close()

    def iter_encoded(self, charset='utf8'):
        for item in self.raw:
            if isinstance(item, str):
                yield item.encode(charset)
            else:
                yield item


class EmmettTestClient(object):
    """This class allows to send requests to a wrapped application."""

    def __init__(
        self, application, response_wrapper=ClientResponse, use_cookies=True,
        allow_subdomain_redirects=False
    ):
        self.application = application
        self.response_wrapper = response_wrapper
        if use_cookies:
            self.cookie_jar = TestCookieJar()
        else:
            self.cookie_jar = None
        self.allow_subdomain_redirects = allow_subdomain_redirects

    def run_asgi_app(self, scope, body):
        if self.cookie_jar is not None:
            self.cookie_jar.inject_asgi(scope)
        rv = run_asgi_app(self.application, scope, body)
        if self.cookie_jar is not None:
            self.cookie_jar.extract_asgi(scope, Headers(rv['headers']))
        return rv

    def resolve_redirect(self, response, new_loc, scope, headers):
        """Resolves a single redirect and triggers the request again
        directly on this redirect client.
        """
        scheme, netloc, script_root, qs, anchor = url_parse(new_loc)
        base_url = url_unparse((scheme, netloc, '', '', '')).rstrip('/') + '/'

        cur_name = netloc.split(':', 1)[0].split('.')
        real_name = get_host(scope, headers).rsplit(':', 1)[0].split('.')

        if len(cur_name) == 1 and not cur_name[0]:
            allowed = True
        else:
            if self.allow_subdomain_redirects:
                allowed = cur_name[-len(real_name):] == real_name
            else:
                allowed = cur_name == real_name

        if not allowed:
            raise RuntimeError('%r does not support redirect to '
                               'external targets' % self.__class__)

        status_code = response['status']
        if status_code == 307:
            method = scope['method']
        else:
            method = 'GET'

        # For redirect handling we temporarily disable the response
        # wrapper.  This is not threadsafe but not a real concern
        # since the test client must not be shared anyways.
        old_response_wrapper = self.response_wrapper
        self.response_wrapper = None
        try:
            return self.open(
                path=script_root, base_url=base_url, query_string=qs,
                method=method, as_tuple=True)
        finally:
            self.response_wrapper = old_response_wrapper

    def open(self, *args, **kwargs):
        as_tuple = kwargs.pop('as_tuple', False)
        follow_redirects = kwargs.pop('follow_redirects', False)
        scope, body = None, b''
        if not kwargs and len(args) == 1:
            if isinstance(args[0], ScopeBuilder):
                scope, body = args[0].get_data()
        if scope is None:
            builder = ScopeBuilder(*args, **kwargs)
            try:
                scope, body = builder.get_data()
            finally:
                builder.close()

        response = self.run_asgi_app(scope, body)

        # handle redirects
        redirect_chain = []
        while 1:
            status_code = response['status']
            if (
                status_code not in (301, 302, 303, 305, 307) or
                not follow_redirects
            ):
                break
            headers = Headers(response['headers'])
            new_location = headers['location']
            if new_location.startswith('/'):
                new_location = (
                    scope['scheme'] + "://" +
                    scope['server'][0] + new_location)
            new_redirect_entry = (new_location, status_code)
            if new_redirect_entry in redirect_chain:
                raise Exception('loop detected')
            redirect_chain.append(new_redirect_entry)
            scope, response = self.resolve_redirect(
                response, new_location, scope, headers)

        if self.response_wrapper is not None:
            response = self.response_wrapper(
                scope['emt.ctx'], response['body'], response['status'],
                Headers(response['headers']))
        if as_tuple:
            return scope, response
        return response

    def get(self, *args, **kw):
        """Like open but method is enforced to GET."""
        kw['method'] = 'GET'
        return self.open(*args, **kw)

    def patch(self, *args, **kw):
        """Like open but method is enforced to PATCH."""
        kw['method'] = 'PATCH'
        return self.open(*args, **kw)

    def post(self, *args, **kw):
        """Like open but method is enforced to POST."""
        kw['method'] = 'POST'
        return self.open(*args, **kw)

    def head(self, *args, **kw):
        """Like open but method is enforced to HEAD."""
        kw['method'] = 'HEAD'
        return self.open(*args, **kw)

    def put(self, *args, **kw):
        """Like open but method is enforced to PUT."""
        kw['method'] = 'PUT'
        return self.open(*args, **kw)

    def delete(self, *args, **kw):
        """Like open but method is enforced to DELETE."""
        kw['method'] = 'DELETE'
        return self.open(*args, **kw)

    def options(self, *args, **kw):
        """Like open but method is enforced to OPTIONS."""
        kw['method'] = 'OPTIONS'
        return self.open(*args, **kw)

    def trace(self, *args, **kw):
        """Like open but method is enforced to TRACE."""
        kw['method'] = 'TRACE'
        return self.open(*args, **kw)

    def __repr__(self):
        return '<%s %r>' % (
            self.__class__.__name__,
            self.application
        )


def run_asgi_app(app, scope, body=b''):
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    request_complete = False
    response_started = False
    response_complete = False
    raw = {"body": BytesIO()}

    async def receive():
        nonlocal request_complete

        if request_complete:
            while not response_complete:
                await asyncio.sleep(0.0001)
            return {"type": "http.disconnect"}

        if isinstance(body, str):
            body_bytes = body.encode("utf-8")
        elif body is None:
            body_bytes = b""
        elif isinstance(body, types.GeneratorType):
            try:
                chunk = body.send(None)
                if isinstance(chunk, str):
                    chunk = chunk.encode("utf-8")
                return {
                    "type": "http.request", "body": chunk, "more_body": True}
            except StopIteration:
                request_complete = True
                return {"type": "http.request", "body": b""}
        else:
            body_bytes = body

        request_complete = True
        return {"type": "http.request", "body": body_bytes}

    async def send(message):
        nonlocal response_started, response_complete

        if message["type"] == "http.response.start":
            raw["version"] = 11
            raw["status"] = message["status"]
            raw["headers"] = [
                (key.decode(), value.decode())
                for key, value in message["headers"]
            ]
            raw["preload_content"] = False
            response_started = True
        elif message["type"] == "http.response.body":
            body = message.get("body", b"")
            more_body = message.get("more_body", False)
            if scope['method'] != "HEAD":
                raw["body"].write(body)
            if not more_body:
                raw["body"].seek(0)
                response_complete = True

    handler = ClientHTTPHandler(app)
    loop.run_until_complete(handler(scope, receive, send))

    return raw
