# -*- coding: utf-8 -*-
"""
    emmett.asgi.handlers
    --------------------

    Provides ASGI handlers.

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

from __future__ import annotations

import asyncio
import os
import re

from collections import OrderedDict
from typing import Any, Awaitable, Callable, Optional, Tuple, Union

from ..ctx import RequestContext, WSContext, current
from ..debug import smart_traceback, debug_handler
from ..http import HTTPResponse, HTTPFile, HTTP
from ..utils import cachedprop
from ..wrappers.helpers import RequestCancelled
from ..wrappers.request import Request
from ..wrappers.response import Response
from ..wrappers.websocket import Websocket
from .typing import Event, EventHandler, EventLooper, Receive, Scope, Send

REGEX_STATIC = re.compile(
    r'^/static/(?P<m>__[\w\-\.]+__/)?(?P<v>_\d+\.\d+\.\d+/)?(?P<f>.*?)$'
)
REGEX_STATIC_LANG = re.compile(
    r'^/(?P<l>\w{2}/)?static/(?P<m>__[\w\-\.]__+/)?(?P<v>_\d+\.\d+\.\d+/)?(?P<f>.*?)$'
)


class EventHandlerWrapper:
    __slots__ = ['event', 'f']

    def __init__(self, event: str, f: EventHandler):
        self.event = event
        self.f = f

    async def __call__(
        self,
        handler: Handler,
        scope: Scope,
        receive: Receive,
        send: Send,
        event: Event
    ) -> Tuple[Optional[EventHandler], None]:
        task = await self.f(handler, scope, receive, send, event)
        return task, None


class MetaHandler(type):
    def __new__(cls, name, bases, attrs):
        new_class = type.__new__(cls, name, bases, attrs)
        declared_events = OrderedDict()
        all_events = OrderedDict()
        events = []
        for key, value in list(attrs.items()):
            if isinstance(value, EventHandlerWrapper):
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
    def on_event(
        cls, event: str
    ) -> Callable[[EventHandler], EventHandlerWrapper]:
        def wrap(f: EventHandler) -> EventHandlerWrapper:
            return EventHandlerWrapper(event, f)
        return wrap

    def get_event_handler(
        self, event_type: str
    ) -> Union[EventHandler, EventHandlerWrapper]:
        return self._events_handlers_.get(event_type, _event_missing)

    def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send
    ) -> Awaitable[None]:
        return self.handle_events(scope, receive, send)

    async def handle_events(
        self,
        scope: Scope,
        receive: Receive,
        send: Send
    ):
        task: Optional[EventLooper] = _event_looper
        event = None
        while task:
            task, event = await task(self, scope, receive, send, event)


class LifeSpanHandler(Handler):
    __slots__ = []

    @Handler.on_event('lifespan.startup')
    async def event_startup(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
        event: Event
    ) -> EventLooper:
        await send({'type': 'lifespan.startup.complete'})
        return _event_looper

    @Handler.on_event('lifespan.shutdown')
    async def event_shutdown(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
        event: Event
    ):
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

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send
    ):
        scope['emt.path'] = scope['path'] or '/'
        try:
            http = await self.pre_handler(scope, receive, send)
            await asyncio.wait_for(
                http.send(scope, send),
                self.app.config.response_timeout
            )
        except RequestCancelled:
            return
        except asyncio.TimeoutError:
            self.app.log.warn(
                f"Timeout sending response: ({scope['emt.path']})"
            )

    @cachedprop
    def error_handler(self) -> Callable[[], Awaitable[str]]:
        return (
            self._debug_handler if self.app.debug else self.exception_handler
        )

    @cachedprop
    def exception_handler(self) -> Callable[[], Awaitable[str]]:
        return self.app.error_handlers.get(500, self._exception_handler)

    @staticmethod
    async def _http_response(code: int) -> HTTPResponse:
        return HTTP(code)

    def _prefix_handler(
        self,
        scope: Scope,
        receive: Receive,
        send: Send
    ) -> Awaitable[HTTPResponse]:
        path = scope['emt.path']
        if not path.startswith(self.router._prefix_main):
            return self._http_response(404)
        scope['emt.path'] = path[self.router._prefix_main_len:] or '/'
        return self.static_handler(scope, receive, send)

    def _static_lang_matcher(
        self, path: str
    ) -> Tuple[Optional[str], Optional[str]]:
        match = REGEX_STATIC_LANG.match(path)
        if match:
            lang, mname, version, file_name = match.group('l', 'm', 'v', 'f')
            if mname:
                mod = self.app._modules.get(mname)
                spath = mod._static_path if mod else self.app.static_path
            else:
                spath = self.app.static_path
            static_file = os.path.join(spath, file_name)
            if lang:
                lang_file = os.path.join(spath, lang, file_name)
                if os.path.exists(lang_file):
                    static_file = lang_file
            return static_file, version
        return None, None

    def _static_nolang_matcher(
        self, path: str
    ) -> Tuple[Optional[str], Optional[str]]:
        if path.startswith('/static'):
            mname, version, file_name = REGEX_STATIC.match(path).group('m', 'v', 'f')
            if mname:
                mod = self.app._modules.get(mname[2:-3])
                static_file = os.path.join(mod._static_path, file_name) if mod else None
            else:
                static_file = os.path.join(self.app.static_path, file_name)
            return static_file, version
        return None, None

    async def _static_response(self, file_path: str) -> HTTPFile:
        return HTTPFile(file_path)

    def _static_handler(
        self,
        scope: Scope,
        receive: Receive,
        send: Send
    ) -> Awaitable[HTTPResponse]:
        path = scope['emt.path']
        #: handle internal assets
        if path.startswith('/__emmett__'):
            file_name = path[12:]
            static_file = os.path.join(
                os.path.dirname(__file__), '..', 'assets', file_name)
            if os.path.splitext(static_file)[1] == 'html':
                return self._http_response(404)
            return self._static_response(static_file)
        #: handle app assets
        static_file, _ = self.static_matcher(path)
        if static_file:
            return self._static_response(static_file)
        return self.dynamic_handler(scope, receive, send)

    async def dynamic_handler(
        self,
        scope: Scope,
        receive: Receive,
        send: Send
    ) -> HTTPResponse:
        ctx = RequestContext(
            self.app,
            scope,
            receive,
            send,
            Request,
            Response
        )
        ctx_token = current._init_(ctx)
        try:
            http = await self.router.dispatch(ctx.request, ctx.response)
        except HTTPResponse as http_exception:
            http = http_exception
            #: render error with handlers if in app
            error_handler = self.app.error_handlers.get(http.status_code)
            if error_handler:
                http = HTTP(
                    http.status_code,
                    await error_handler(),
                    headers=ctx.response.headers,
                    cookies=ctx.response.cookies
                )
        except RequestCancelled:
            raise
        except Exception:
            self.app.log.exception('Application exception:')
            http = HTTP(
                500,
                await self.error_handler(),
                headers=ctx.response.headers
            )
        finally:
            current._close_(ctx_token)
        return http

    async def _debug_handler(self) -> str:
        current.response.headers._data['content-type'] = (
            'text/html; charset=utf-8'
        )
        return debug_handler(smart_traceback(self.app))

    async def _exception_handler(self) -> str:
        current.response.headers._data['content-type'] = 'text/plain'
        return 'Internal error'


class WSHandler(RequestHandler):
    __slots__ = ['pre_handler']

    def _bind_router(self):
        self.router = self.app._router_ws

    def _configure_methods(self):
        self.pre_handler = (
            self._prefix_handler if self.router._prefix_main else
            self.dynamic_handler)

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send
    ):
        scope['emt.input'] = asyncio.Queue()
        task_events = asyncio.create_task(
            self.handle_events(scope, receive, send))
        task_request = asyncio.create_task(
            self.handle_request(scope, receive, send))
        _, pending = await asyncio.wait(
            [task_request, task_events], return_when=asyncio.FIRST_COMPLETED
        )
        scope['emt._flow_cancel'] = True
        _cancel_tasks(pending)

    @Handler.on_event('websocket.connect')
    async def event_connect(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
        event: Event
    ) -> EventLooper:
        return _event_looper

    @Handler.on_event('websocket.disconnect')
    async def event_disconnect(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
        event: Event
    ):
        return

    @Handler.on_event('websocket.receive')
    async def event_receive(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
        event: Event
    ) -> EventLooper:
        await scope['emt.input'].put(event.get('bytes') or event['text'])
        return _event_looper

    async def handle_request(
        self,
        scope: Scope,
        receive: Receive,
        send: Send
    ):
        scope['emt.path'] = scope['path'] or '/'
        scope['emt._ws_closed'] = False
        try:
            await self.pre_handler(scope, receive, send)
        except HTTPResponse:
            if not scope['emt._ws_closed']:
                await send({'type': 'websocket.close', 'code': 1006})
        except asyncio.CancelledError:
            if not scope.get('emt._flow_cancel', False):
                self.app.log.exception('Application exception:')
        except Exception:
            if not scope['emt._ws_closed']:
                await send({'type': 'websocket.close', 'code': 1006})
            self.app.log.exception('Application exception:')

    def _prefix_handler(
        self,
        scope: Scope,
        receive: Receive,
        send: Send
    ) -> Awaitable[None]:
        path = scope['emt.path']
        if not path.startswith(self.router._prefix_main):
            raise HTTP(404)
        scope['emt.path'] = path[self.router._prefix_main_len:] or '/'
        return self.dynamic_handler(scope, receive, send)

    async def dynamic_handler(
        self,
        scope: Scope,
        receive: Receive,
        send: Send
    ):
        ctx = WSContext(
            self.app,
            scope,
            scope['emt.input'].get,
            send,
            Websocket
        )
        ctx_token = current._init_(ctx)
        try:
            await self.router.dispatch(ctx.websocket)
        finally:
            if (
                not scope.get('emt._flow_cancel', False) and
                ctx.websocket._accepted
            ):
                await send({'type': 'websocket.close', 'code': 1000})
                scope['emt._ws_closed'] = True
            current._close_(ctx_token)


async def _event_looper(
    handler: Handler,
    scope: Scope,
    receive: Receive,
    send: Send,
    event: Any = None
) -> Tuple[Union[EventHandler, EventHandlerWrapper], Event]:
    event = await receive()
    event_handler = handler.get_event_handler(event['type'])
    return event_handler, event


async def _event_missing(
    handler: Handler,
    scope: Scope,
    receive: Receive,
    send: Send,
    event: Event
):
    raise RuntimeError(f"Event type '{event['type']}' not recognized")


def _cancel_tasks(tasks):
    for task in tasks:
        task.cancel()
