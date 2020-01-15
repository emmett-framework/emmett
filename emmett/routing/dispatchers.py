# -*- coding: utf-8 -*-
"""
    emmett.routing.dispatchers
    --------------------------

    Provides pipeline dispatchers for routes.

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

import asyncio

from ..ctx import current


class Dispatcher:
    __slots__ = ['f', 'flow_open', 'flow_close']

    def __init__(self, route):
        self.f = route.f
        self.flow_open = route.pipeline_flow_open
        self.flow_close = route.pipeline_flow_close

    async def _parallel_flow(self, flow):
        tasks = [asyncio.create_task(method()) for method in flow]
        await asyncio.gather(*tasks, return_exceptions=True)
        for task in tasks:
            if task.exception():
                raise task.exception()

    def dispatch(self, wrapper, reqargs):
        raise NotImplementedError


class RequestDispatcher(Dispatcher):
    __slots__ = ['response_builders']

    def __init__(self, route, rule):
        super().__init__(route)
        self.response_builders = rule.response_builders

    async def get_response(self, wrapper, reqargs):
        return self.response_builders[wrapper.method](await self.f(**reqargs))

    def dispatch(self, wrapper, reqargs):
        return self.get_response(wrapper, reqargs)


class RequestOpenDispatcher(RequestDispatcher):
    __slots__ = []

    async def dispatch(self, wrapper, reqargs):
        await self._parallel_flow(self.flow_open)
        return await self.get_response(wrapper, reqargs)


class RequestCloseDispatcher(RequestDispatcher):
    __slots__ = []

    async def dispatch(self, wrapper, reqargs):
        try:
            rv = await self.get_response(wrapper, reqargs)
        except Exception:
            await self._parallel_flow(self.flow_close)
            raise
        await self._parallel_flow(self.flow_close)
        return rv


class RequestFlowDispatcher(RequestDispatcher):
    __slots__ = []

    async def dispatch(self, wrapper, reqargs):
        await self._parallel_flow(self.flow_open)
        try:
            rv = await self.get_response(wrapper, reqargs)
        except Exception:
            await self._parallel_flow(self.flow_close)
            raise
        await self._parallel_flow(self.flow_close)
        return rv


class WSDispatcher(Dispatcher):
    __slots__ = []

    def dispatch(self, wrapper, reqargs):
        return self.f(**reqargs)


class WSOpenDispatcher(WSDispatcher):
    __slots__ = []

    async def dispatch(self, wrapper, reqargs):
        await self._parallel_flow(self.flow_open)
        await self.f(**reqargs)


class WSCloseDispatcher(WSDispatcher):
    __slots__ = []

    async def dispatch(self, wrapper, reqargs):
        try:
            await self.f(**reqargs)
        except Exception:
            await self._parallel_flow(self.flow_close)
            raise
        await asyncio.shield(self._parallel_flow(self.flow_close))


class WSFlowDispatcher(WSDispatcher):
    __slots__ = []

    async def dispatch(self, wrapper, reqargs):
        await self._parallel_flow(self.flow_open)
        try:
            await self.f(**reqargs)
        except Exception:
            await self._parallel_flow(self.flow_close)
            raise
        await asyncio.shield(self._parallel_flow(self.flow_close))


class DispatcherCacheMixin:
    __slots__ = []
    _allowed_methods = {'GET', 'HEAD'}

    def __init__(self, route, rule):
        super().__init__(route, rule)
        self.route = route
        self.cache_rule = rule.cache_rule

    async def get_response(self, wrapper, reqargs):
        if wrapper.method not in self._allowed_methods:
            return await super().get_response(wrapper, reqargs)
        response = current.response
        key = self.cache_rule._build_ctx_key(
            self.route, **self.cache_rule._build_ctx(
                reqargs, self.route, current))
        data = self.cache_rule.cache.get(key)
        if data is not None:
            response.headers.update(data['headers'])
            return data['http_cls'], data['content']
        http_cls, output = await super().get_response(wrapper, reqargs)
        if response.status == 200:
            self.cache_rule.cache.set(
                key, {
                    'http_cls': http_cls,
                    'content': output,
                    'headers': response.headers},
                self.cache_rule.duration)
        return http_cls, output


class CacheDispatcher(DispatcherCacheMixin, RequestDispatcher):
    __slots__ = ('route', 'cache_rule')


class CacheOpenDispatcher(DispatcherCacheMixin, RequestOpenDispatcher):
    __slots__ = ('route', 'cache_rule')


class CacheCloseDispatcher(DispatcherCacheMixin, RequestCloseDispatcher):
    __slots__ = ('route', 'cache_rule')


class CacheFlowDispatcher(DispatcherCacheMixin, RequestFlowDispatcher):
    __slots__ = ('route', 'cache_rule')
