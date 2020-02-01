# -*- coding: utf-8 -*-
"""
    emmett.asgi.handlers
    --------------------

    Provides ASGI handlers.

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

import asyncio
import os
import re

from collections import OrderedDict
from datetime import datetime

from ..ctx import Context, current
from ..debug import smart_traceback, debug_handler
from ..http import HTTPResponse, HTTPFile, HTTP
from ..language import T
from ..utils import cachedprop
from ..wrappers.request import Body, Request
from ..wrappers.response import Response
from ..wrappers.websocket import Websocket

REGEX_STATIC = re.compile(
    '^/static/(?P<v>_\d+\.\d+\.\d+/)?(?P<f>.*?)$')
REGEX_STATIC_LANG = re.compile(
    '^/(?P<l>\w+/)?static/(?P<v>_\d+\.\d+\.\d+/)?(?P<f>.*?)$')


class HandlerEvent:
    __slots__ = ['event', 'f']

    def __init__(self, event, f):
        self.event = event
        self.f = f

    async def __call__(self, *args, **kwargs):
        task = await self.f(*args, **kwargs)
        return task, None


class MetaHandler(type):
    def __new__(cls, name, bases, attrs):
        new_class = type.__new__(cls, name, bases, attrs)
        declared_events = OrderedDict()
        all_events = OrderedDict()
        events = []
        for key, value in list(attrs.items()):
            if isinstance(value, HandlerEvent):
                events.append((key, value))
        declared_events.update(events)
        new_class._declared_events_ = declared_events
        for base in reversed(new_class.__mro__[1:]):
            if hasattr(base, '_declared_events_'):
                all_events.update(base._declared_events_)
        all_events.update(declared_events)
        new_class._all_events_ = all_events
        new_class._events_handlers_ = {
            el.event: el for el in new_class._all_events_.values()}
        return new_class


class Handler(metaclass=MetaHandler):
    __slots__ = ['app']

    def __init__(self, app):
        self.app = app

    @classmethod
    def on_event(cls, event):
        def wrap(f):
            return HandlerEvent(event, f)
        return wrap

    def get_event_handler(self, event_type):
        return self._events_handlers_.get(event_type, _event_looper)

    async def __call__(self, scope, receive, send):
        await self.handle_events(scope, receive, send)

    async def handle_events(self, scope, receive, send):
        task, event = _event_looper, None
        while task:
            task, event = await task(self, scope, receive, send, event)


class LifeSpanHandler(Handler):
    @Handler.on_event('lifespan.startup')
    async def event_startup(self, scope, receive, send, event):
        await send({'type': 'lifespan.startup.complete'})
        return _event_looper

    @Handler.on_event('lifespan.shutdown')
    async def event_shutdown(self, scope, receive, send, event):
        await send({'type': 'lifespan.shutdown.complete'})


class RequestHandler(Handler):
    __slots__ = ['router']

    def __init__(self, app):
        super().__init__(app)
        self._bind_router()
        self._configure_methods()

    def _bind_router(self):
        raise NotImplementedError

    def _configure_methods(self):
        raise NotImplementedError


class HTTPHandler(RequestHandler):
    __slots__ = ['pre_handler', 'static_handler', 'static_matcher', '__dict__']

    def _bind_router(self):
        self.router = self.app._router_http

    def _configure_methods(self):
        self.static_matcher = (
            self._static_lang_matcher if self.app.language_force_on_url else
            self._static_nolang_matcher)
        self.static_handler = (
            self._static_handler if self.app.config.handle_static else
            self.dynamic_handler)
        self.pre_handler = (
            self._prefix_handler if self.router._prefix_main else
            self.static_handler)

    async def __call__(self, scope, receive, send):
        scope['emt.path'] = scope['path'] or '/'
        scope['emt.now'] = datetime.utcnow()
        scope['emt.input'] = Body(self.app.config.request_max_content_length)
        task_events = asyncio.create_task(
            self.handle_events(scope, receive, send))
        task_request = asyncio.create_task(
            self.handle_request(scope, receive, send))
        _, pending = await asyncio.wait(
            [task_request, task_events], return_when=asyncio.FIRST_COMPLETED
        )
        await _cancel_tasks(pending)

    @Handler.on_event('http.disconnect')
    async def event_disconnect(self, scope, receive, send, event):
        return

    @Handler.on_event('http.request')
    async def event_request(self, scope, receive, send, event):
        scope['emt.input'].append(event['body'])
        if not event.get('more_body', False):
            scope['emt.input'].set_complete()
        return _event_looper

    @cachedprop
    def error_handler(self):
        return (
            self._debug_handler if self.app.debug else self.exception_handler)

    @cachedprop
    def exception_handler(self):
        return self.app.error_handlers.get(500, self._exception_handler)

    async def handle_request(self, scope, receive, send):
        try:
            http = await asyncio.shield(self.pre_handler(scope, receive, send))
        except HTTPResponse as httpe:
            http = httpe
        except asyncio.CancelledError:
            return
        # TODO: timeout from app config/response
        await asyncio.wait_for(http.send(scope, send), None)

    def _prefix_handler(self, scope, receive, send):
        path = current.request.path
        if not path.startswith(self.router._prefix_main):
            return HTTP(404)
        current.request.path = scope['emt.path'] = (
            path[self.router._prefix_main_len:] or '/')
        return self.static_handler(scope, receive, send)

    def _static_lang_matcher(self, path):
        match = REGEX_STATIC_LANG.match(path)
        if match:
            lang, version, file_name = match.group('l', 'v', 'f')
            static_file = os.path.join(self.app.static_path, file_name)
            if lang:
                lang_file = os.path.join(self.app.static_path, lang, file_name)
                if os.path.exists(lang_file):
                    static_file = lang_file
            return static_file, version
        return None, None

    def _static_nolang_matcher(self, path):
        if path.startswith('/static'):
            version, file_name = REGEX_STATIC.match(path).group('v', 'f')
            static_file = os.path.join(self.app.static_path, file_name)
            return static_file, version
        return None, None

    async def _static_response(self, file_path):
        return HTTPFile(file_path)

    def _static_handler(self, scope, receive, send):
        path = scope['emt.path']
        #: handle internal assets
        if path.startswith('/__emmett__'):
            file_name = path[12:]
            static_file = os.path.join(
                os.path.dirname(__file__), '..', 'assets', file_name)
            if os.path.splitext(static_file)[1] == 'html':
                return HTTP(404)
            return self._static_response(static_file)
        #: handle app assets
        static_file, version = self.static_matcher(path)
        if static_file:
            return self._static_response(static_file)
        return self.dynamic_handler(scope, receive, send)

    async def dynamic_handler(self, scope, receive, send):
        try:
            ctx_token = current._init_(RequestContext, self.app, scope)
            http = await self.router.dispatch()
        except HTTPResponse as http_exception:
            http = http_exception
            #: render error with handlers if in app
            error_handler = self.app.error_handlers.get(http.status_code)
            if error_handler:
                http = HTTP(
                    http.status_code,
                    await error_handler(),
                    current.response.headers
                )
            #: always set cookies
            http.set_cookies(current.response.cookies)
        except Exception:
            self.app.log.exception('Application exception:')
            raise HTTP(
                500,
                await self.error_handler(),
                headers=current.response.headers
            )
        finally:
            current._close_(ctx_token)
        return http

    async def _debug_handler(self):
        return debug_handler(smart_traceback(self.app))

    async def _exception_handler(self):
        current.response.headers['Content-Type'] = 'text/plain'
        return 'Internal error'


class WSHandler(RequestHandler):
    __slots__ = ['pre_handler']

    def _bind_router(self):
        self.router = self.app._router_ws

    def _configure_methods(self):
        self.pre_handler = (
            self._prefix_handler if self.router._prefix_main else
            self.dynamic_handler)

    async def __call__(self, scope, receive, send):
        scope['emt.path'] = scope['path'] or '/'
        scope['emt.input'] = asyncio.Queue()
        task_events = asyncio.create_task(
            self.handle_events(scope, receive, send))
        task_request = asyncio.create_task(
            self.handle_request(scope, receive, send))
        _, pending = await asyncio.wait(
            [task_request, task_events], return_when=asyncio.FIRST_COMPLETED
        )
        scope['emt._flow_cancel'] = True
        await _cancel_tasks(pending)

    @Handler.on_event('websocket.disconnect')
    async def event_disconnect(self, scope, receive, send, event):
        return

    @Handler.on_event('websocket.receive')
    async def event_receive(self, scope, receive, send, event):
        await scope['emt.input'].put(event.get('bytes') or event['text'])
        return _event_looper

    async def handle_request(self, scope, receive, send):
        try:
            await self.pre_handler(scope, receive, send)
        except asyncio.CancelledError:
            if not scope.get('emt._flow_cancel', False):
                self.app.log.exception('Application exception:')
        except Exception:
            self.app.log.exception('Application exception:')

    def _prefix_handler(self, scope, receive, send):
        path = current.request.path
        if not path.startswith(self.router._prefix_main):
            return HTTP(404)
        current.request.path = scope['emt.path'] = (
            path[self.router._prefix_main_len:] or '/')
        return self.dynamic_handler(scope, receive, send)

    async def dynamic_handler(self, scope, receive, send):
        ctx_token = current._init_(
            WSContext, self.app, scope, scope['emt.input'].get, send
        )
        try:
            await self.router.dispatch()
        finally:
            if current.websocket._accepted:
                await send({'type': 'websocket.close', 'code': 1000})
            current._close_(ctx_token)


class RequestContext:
    def __init__(self, app, scope):
        self.app = app
        self.request = Request(
            scope,
            app.config.request_max_content_length,
            app.config.request_body_timeout
        )
        self.response = Response()
        self.session = None

    @property
    def now(self):
        return self.request.now

    @cachedprop
    def language(self):
        return self.request.accept_language.best_match(list(T._langmap))


class WSContext(Context):
    def __init__(self, app, scope, receive, send):
        self.app = app
        self.websocket = Websocket(
            scope,
            receive,
            send
        )
        self.session = None

    @cachedprop
    def language(self):
        return self.websocket.accept_language.best_match(list(T._langmap))


async def _event_looper(handler, scope, receive, send, event):
    event = await receive()
    event_handler = handler.get_event_handler(event['type'])
    return event_handler, event


async def _event_missing(handler, receive, send):
    raise RuntimeError('Event type not recognized.')


async def _cancel_tasks(tasks):
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
