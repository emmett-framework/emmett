# -*- coding: utf-8 -*-
"""
    weppy.routing.dispatchers
    -------------------------

    Provides pipeline dispatchers for http routes.

    :copyright: (c) 2014-2019 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

import asyncio

from ..ctx import current


class Dispatcher:
    __slots__ = ('f', 'flow_open', 'flow_close', 'response_builders')

    def __init__(self, route, rule):
        self.f = route.f
        self.flow_open = route.pipeline_flow_open
        self.flow_close = route.pipeline_flow_close
        self.response_builders = rule.response_builders

    async def _parallel_flow(self, flow):
        tasks = [asyncio.create_task(method()) for method in flow]
        await asyncio.gather(*tasks, return_exceptions=True)
        for task in tasks:
            if task.exception():
                raise task.exception()

    def before_dispatch(self):
        return self._parallel_flow(self.flow_open)

    def after_dispatch(self):
        return self._parallel_flow(self.flow_close)

    def build_response(self, request, output):
        return self.response_builders[request.method](output)

    async def get_response(self, request, reqargs):
        return self.build_response(request, await self.f(**reqargs))

    def dispatch(self, request, reqargs):
        return self.get_response(request, reqargs)


class BeforeDispatcher(Dispatcher):
    __slots__ = ()

    async def dispatch(self, request, reqargs):
        await self.before_dispatch()
        return await self.get_response(request, reqargs)


class AfterDispatcher(Dispatcher):
    __slots__ = ()

    async def dispatch(self, request, reqargs):
        try:
            rv = await self.get_response(request, reqargs)
        except Exception:
            await self.after_dispatch()
            raise
        await self.after_dispatch()
        return rv


class CompleteDispatcher(Dispatcher):
    __slots__ = ()

    async def dispatch(self, request, reqargs):
        await self.before_dispatch()
        try:
            rv = await self.get_response(request, reqargs)
        except Exception:
            await self.after_dispatch()
            raise
        await self.after_dispatch()
        return rv


class DispatcherCacheMixin:
    __slots__ = ()
    _allowed_methods = {'GET', 'HEAD'}

    def __init__(self, route, rule):
        super().__init__(route, rule)
        self.route = route
        self.cache_rule = rule.cache_rule

    async def get_response(self, request, reqargs):
        if request.method not in self._allowed_methods:
            return await super().get_response(request, reqargs)
        response = current.response
        key = self.cache_rule._build_ctx_key(
            self.route, **self.cache_rule._build_ctx(
                reqargs, self.route, current))
        data = self.cache_rule.cache.get(key)
        if data is not None:
            response.headers.update(data['headers'])
            return data['http_cls'], data['content']
        http_cls, output = await super().get_response(request, reqargs)
        if response.status == 200:
            self.cache_rule.cache.set(
                key, {
                    'http_cls': http_cls,
                    'content': output,
                    'headers': response.headers},
                self.cache_rule.duration)
        return http_cls, output


class CacheDispatcher(DispatcherCacheMixin, Dispatcher):
    __slots__ = ('route', 'cache_rule')


class BeforeCacheDispatcher(DispatcherCacheMixin, BeforeDispatcher):
    __slots__ = ('route', 'cache_rule')


class AfterCacheDispatcher(DispatcherCacheMixin, AfterDispatcher):
    __slots__ = ('route', 'cache_rule')


class CompleteCacheDispatcher(DispatcherCacheMixin, CompleteDispatcher):
    __slots__ = ('route', 'cache_rule')
