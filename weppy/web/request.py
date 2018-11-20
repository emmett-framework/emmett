# -*- coding: utf-8 -*-

import asyncio
import pendulum

from http.cookies import SimpleCookie

from ..utils import cachedprop, cachedasyncprop


class Body(object):
    __slots__ = ('_data', '_complete', '_max_content_length')

    def __init__(self, max_content_length=None):
        self._data = bytearray()
        self._complete = asyncio.Event()
        # self._has_data = asyncio.Event()
        self._max_content_length = max_content_length

    # def __aiter__(self):
    #     return self

    # async def __anext__(self) -> bytes:
    #     # If the first time through was the entirety of the data,
    #     # set_complete was already called so we have to wait on both
    #     # _has_data and _complete otherwise we'll hang indefinitely
    #     # waiting for _has_data since it will never get set again
    #     await asyncio.wait(
    #         [self._has_data.wait(), self._complete.wait()], return_when=asyncio.FIRST_COMPLETED,
    #     )
    #     if self._complete.is_set() and len(self._data) == 0:
    #         raise StopAsyncIteration()

    #     data = bytes(self._data)
    #     self._data.clear()
    #     self._has_data.clear()
    #     return data

    async def __await__(self):
        await self._complete.wait()
        return bytes(self._data)

    def append(self, data):
        if data == b'':
            return
        self._data.extend(data)
        # self._has_data.set()
        # if self._max_content_length is not None and len(self._data) > self._max_content_length:
        #     from ..exceptions import RequestEntityTooLarge  # noqa Avoiding circular import
        #     raise RequestEntityTooLarge()

    def set_complete(self):
        self._complete.set()
        # self._has_data.set()


class Request(object):
    def __init__(self, scope, max_content_length=None, body_timeout=None):
        self._scope = scope
        print(scope)
        self.max_content_length = max_content_length
        self.body_timeout = body_timeout
        self.scheme = scope['scheme']
        self.hostname = None
        self.method = scope['method']
        self.path = scope['path']
        # if (
        #     self.content_length is not None and self.max_content_length is not None and
        #     self.content_length > self.max_content_length
        # ):
        #     from ..exceptions import RequestEntityTooLarge  # noqa Avoiding circular import
        #     raise RequestEntityTooLarge()
        # self._input = Body(self.max_content_length)
        self._input = scope['emt.input']

    @cachedasyncprop
    async def body(self):
        try:
            print('ensuring body_future')
            # body_future = asyncio.ensure_future(self._input)
            # rv = await asyncio.wait_for(body_future, timeout=self.body_timeout)
            rv = await asyncio.wait_for(self._input, timeout=self.body_timeout)
        except asyncio.TimeoutError:
            # body_future.cancel()
            # from ..exceptions import RequestTimeout
            # raise RequestTimeout()
            raise
        return rv

    @cachedprop
    def now(self):
        return pendulum.instance(self._scope['emt.now'])

    @cachedprop
    def now_local(self):
        return self.now.in_timezone(pendulum.local_timezone())

    @cachedprop
    def cookies(self):
        cookies = SimpleCookie()
        # for cookie in self.environ.get('HTTP_COOKIE', '').split(';'):
        #     cookies.load(cookie)
        return cookies
