# -*- coding: utf-8 -*-

import asyncio

from collections import OrderedDict
from datetime import datetime

from ..ctx import current
from ..http import HTTP
from ..utils import cachedprop


class HandlerEvent(object):
    __slots__ = ('event', 'f')

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
        await self.handle_events(receive, send)

    async def handle_events(self, receive, send):
        task, event = _event_looper, None
        while task:
            task, event = await task(self, receive, send, event)


class LifeSpanHandler(Handler):
    @Handler.on_event('lifespan.startup')
    async def event_startup(self, receive, send, event):
        await send({'type': 'lifespan.startup.complete'})
        return _event_looper

    @Handler.on_event('lifespan.shutdown')
    async def event_shutdown(self, receive, send, event):
        await send({'type': 'lifespan.shutdown.complete'})


class RequestHandler(Handler):
    async def __call__(self, scope, receive, send):
        scope['emt.now'] = datetime.utcnow()
        task_request = asyncio.ensure_future(self.handle_request(scope, send))
        task_events = asyncio.ensure_future(self.handle_events(receive, send))
        _, pending = await asyncio.wait(
            [task_request, task_events], return_when=asyncio.FIRST_COMPLETED
        )
        await _cancel_tasks(pending)

    async def handle_request(self, scope, send):
        raise NotImplementedError


class HTTPHandler(RequestHandler):
    @Handler.on_event('http.disconnect')
    async def event_disconnect(self, receive, send, event):
        return

    @Handler.on_event('http.request')
    async def event_request(self, receive, send, event):
        current.request._input.append(event['body'])
        if not event.get('more_body', False):
            current.request._input.set_complete()

    @cachedprop
    def pre_handler(self):
        return (
            self._prefix_handler if self.app.route._prefix_main else
            self._pre_handler)

    @cachedprop
    def static_handler(self):
        return (
            self._static_handler if self.app.config.handle_static else
            self.dynamic_handler)

    async def handle_request(self, scope, send):
        try:
            http = await self.pre_handler(scope, send)
        except Exception:
            if self.app.debug:
                from ..debug import smart_traceback, debug_handler
                tb = smart_traceback(self.app)
                body = debug_handler(tb)
            else:
                body = None
                custom_handler = self.app.error_handlers.get(500, lambda: None)
                try:
                    body = custom_handler()
                except Exception:
                    pass
                if not body:
                    body = '<html><body>Internal error</body></html>'
            self.app.log.exception('Application exception:')
            http = HTTP(500, body)
        await http.send(send)

    async def _pre_handler(self, scope, send):
        scope['emt.path'] = scope['path'] or '/'
        return await self.static_handler(scope, send)

    async def _prefix_handler(self, scope, send):
        path = scope['path'] or '/'
        if not path.startswith(self.app.route._prefix_main):
            return HTTP(404)
        scope['emt.path'] = path[self.app.route._prefix_main_len:] or '/'
        return await self.static_handler(scope, send)

    async def _static_handler(self, scope, send):
        # TODO: stream handling
        return await self.dynamic_handler(scope, send)

    async def dynamic_handler(self, scope, send):
        ctx_token = current._init_(scope)
        response = current.response
        try:
            await self.app.route.dispatch()
            http = HTTP(
                response.status, response.output,
                response.headers, response.cookies)
        except HTTP as httpe:
            http = httpe
            #: render error with handlers if in app
            error_handler = self.app.error_handlers.get(http.status_code)
            if error_handler:
                output = error_handler()
                http = HTTP(http.status_code, output, http.headers)
            #: always set cookies
            http.set_cookies(response.cookies)
        finally:
            current._close_(ctx_token)
        return http


class WSHandler(RequestHandler):
    pass


async def _event_looper(handler, receive, send, event):
    event = await receive()
    event_handler = handler.get_event_handler(event['type'])
    return event_handler, event


async def _event_missing(handler, receive, send):
    raise RuntimeError('Event type not recognized.')


async def _cancel_tasks(tasks):
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    for task in tasks:
        if not task.cancelled() and task.exception() is not None:
            raise task.exception()
