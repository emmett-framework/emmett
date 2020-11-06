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

    def dispatch(self, reqargs):
        return self.f(**reqargs)


class RequestDispatcher(Dispatcher):
    __slots__ = ['response_builder']

    def __init__(self, route, rule, response_builder):
        super().__init__(route)
        self.response_builder = response_builder

    async def dispatch(self, reqargs, response):
        return self.response_builder(await self.f(**reqargs), response)


class RequestOpenDispatcher(RequestDispatcher):
    __slots__ = []

    async def dispatch(self, reqargs, response):
        await self._parallel_flow(self.flow_open)
        return self.response_builder(await self.f(**reqargs), response)


class RequestCloseDispatcher(RequestDispatcher):
    __slots__ = []

    async def dispatch(self, reqargs, response):
        try:
            rv = self.response_builder(await self.f(**reqargs), response)
        finally:
            await self._parallel_flow(self.flow_close)
        return rv


class RequestFlowDispatcher(RequestDispatcher):
    __slots__ = []

    async def dispatch(self, reqargs, response):
        await self._parallel_flow(self.flow_open)
        try:
            rv = self.response_builder(await self.f(**reqargs), response)
        finally:
            await self._parallel_flow(self.flow_close)
        return rv


class WSOpenDispatcher(Dispatcher):
    __slots__ = []

    async def dispatch(self, reqargs):
        await self._parallel_flow(self.flow_open)
        await self.f(**reqargs)


class WSCloseDispatcher(Dispatcher):
    __slots__ = []

    async def dispatch(self, reqargs):
        try:
            await self.f(**reqargs)
        except Exception:
            await self._parallel_flow(self.flow_close)
            raise
        await asyncio.shield(self._parallel_flow(self.flow_close))


class WSFlowDispatcher(Dispatcher):
    __slots__ = []

    async def dispatch(self, reqargs):
        await self._parallel_flow(self.flow_open)
        try:
            await self.f(**reqargs)
        except Exception:
            await self._parallel_flow(self.flow_close)
            raise
        await asyncio.shield(self._parallel_flow(self.flow_close))


class CacheDispatcher(RequestDispatcher):
    __slots__ = ['route', 'cache_rule']

    def __init__(self, route, rule, response_builder):
        super().__init__(route, rule, response_builder)
        self.route = route
        self.cache_rule = rule.cache_rule

    async def get_data(self, reqargs, response):
        key = self.cache_rule._build_ctx_key(
            self.route, **self.cache_rule._build_ctx(
                reqargs, self.route, current
            )
        )
        data = self.cache_rule.cache.get(key)
        if data is not None:
            response.headers.update(data['headers'])
            return data['content']
        content = await self.f(**reqargs)
        if response.status == 200:
            self.cache_rule.cache.set(
                key,
                {'content': content, 'headers': response.headers},
                self.cache_rule.duration
            )
        return content

    async def dispatch(self, reqargs, response):
        content = await self.get_data(reqargs, response)
        return self.response_builder(content, response)


class CacheOpenDispatcher(CacheDispatcher):
    __slots__ = []

    async def dispatch(self, reqargs, response):
        await self._parallel_flow(self.flow_open)
        return await super().dispatch(reqargs, response)


class CacheCloseDispatcher(CacheDispatcher):
    __slots__ = []

    async def dispatch(self, reqargs, response):
        try:
            content = await self.get_data(reqargs, response)
        except Exception:
            await self._parallel_flow(self.flow_close)
            raise
        await self._parallel_flow(self.flow_close)
        return self.response_builder(content, response)


class CacheFlowDispatcher(CacheDispatcher):
    __slots__ = []

    async def dispatch(self, reqargs, response):
        await self._parallel_flow(self.flow_open)
        try:
            content = await self.get_data(reqargs, response)
        except Exception:
            await self._parallel_flow(self.flow_close)
            raise
        await self._parallel_flow(self.flow_close)
        return self.response_builder(content, response)
