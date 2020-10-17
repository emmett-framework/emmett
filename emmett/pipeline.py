# -*- coding: utf-8 -*-
"""
    emmett.pipeline
    ---------------

    Provides the pipeline classes.

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

import asyncio
import types

from functools import wraps
from typing import Optional

from .helpers import flash
from .http import HTTPResponse, redirect


class Pipeline:
    __slots__ = ['_method_open', '_method_close', 'pipes']
    _type_suffix = ''

    def __init__(self, pipes=[]):
        self._method_open = f'open_{self._type_suffix}'
        self._method_close = f'close_{self._type_suffix}'
        self.pipes = pipes

    @staticmethod
    def _awaitable_wrap(f):
        @wraps(f)
        async def awaitable(*args, **kwargs):
            return f(*args, **kwargs)
        return awaitable

    def __call__(self, f):
        raise NotImplementedError

    def _flow_open(self):
        rv = []
        for pipe in self.pipes:
            if pipe._pipeline_all_methods_.issuperset(
                {'open', self._method_open}
            ):
                raise RuntimeError(
                    f'{pipe.__class__.__name__} pipe has double open methods.'
                    f' Use `open` or `{self._method_open}`, not both.'
                )
            if 'open' in pipe._pipeline_all_methods_:
                rv.append(pipe.open)
            if self._method_open in pipe._pipeline_all_methods_:
                rv.append(getattr(pipe, self._method_open))
        return rv

    def _flow_close(self):
        rv = []
        for pipe in reversed(self.pipes):
            if pipe._pipeline_all_methods_.issuperset(
                {'close', self._method_close}
            ):
                raise RuntimeError(
                    f'{pipe.__class__.__name__} pipe has double close methods.'
                    f' Use `close` or `{self._method_close}`, not both.'
                )
            if 'close' in pipe._pipeline_all_methods_:
                rv.append(pipe.close)
            if self._method_close in pipe._pipeline_all_methods_:
                rv.append(getattr(pipe, self._method_close))
        return rv


class RequestPipeline(Pipeline):
    __slots__ = []
    _type_suffix = 'request'

    def _get_proper_wrapper(self, pipe):
        if pipe._pipeline_all_methods_.issuperset(
            {'on_pipe_success', 'on_pipe_failure'}
        ):
            rv = _wrap_flow_request_complete
        elif 'on_pipe_success' in pipe._pipeline_all_methods_:
            rv = _wrap_flow_request_success
        elif 'on_pipe_failure' in pipe._pipeline_all_methods_:
            rv = _wrap_flow_request_failure
        else:
            rv = _wrap_flow_request_basic
        return rv

    def __call__(self, f):
        if not asyncio.iscoroutinefunction(f):
            f = self._awaitable_wrap(f)
        for pipe in reversed(self.pipes):
            if not isinstance(pipe, Pipe):
                continue
            if not pipe._is_flow_request_responsible:
                continue
            wrapper = self._get_proper_wrapper(pipe)
            pipe_method = (
                pipe.pipe_request
                if 'pipe_request' in pipe._pipeline_all_methods_
                else pipe.pipe)
            f = wrapper(
                pipe_method, pipe.on_pipe_success, pipe.on_pipe_failure, f)
        return f

    def _output_type(self):
        rv = None
        for pipe in reversed(self.pipes):
            if not pipe._is_flow_request_responsible or pipe.output is None:
                continue
            rv = pipe.output
        return rv


class WebsocketPipeline(Pipeline):
    __slots__ = []
    _type_suffix = 'ws'

    def _get_proper_wrapper(self, pipe):
        if pipe._pipeline_all_methods_.issuperset(
            {'on_pipe_success', 'on_pipe_failure'}
        ):
            rv = _wrap_flow_ws_complete
        elif 'on_pipe_success' in pipe._pipeline_all_methods_:
            rv = _wrap_flow_ws_success
        elif 'on_pipe_failure' in pipe._pipeline_all_methods_:
            rv = _wrap_flow_ws_failure
        else:
            rv = _wrap_flow_ws_basic
        return rv

    def __call__(self, f):
        if not asyncio.iscoroutinefunction(f):
            f = self._awaitable_wrap(f)
        for pipe in reversed(self.pipes):
            if not isinstance(pipe, Pipe):
                continue
            if not pipe._is_flow_ws_responsible:
                continue
            wrapper = self._get_proper_wrapper(pipe)
            pipe_method = (
                pipe.pipe_ws
                if 'pipe_ws' in pipe._pipeline_all_methods_
                else pipe.pipe)
            f = wrapper(
                pipe_method, pipe.on_pipe_success, pipe.on_pipe_failure, f)
        return f

    def _flow_receive(self):
        rv = []
        for pipe in self.pipes:
            if 'on_receive' not in pipe._pipeline_all_methods_:
                continue
            rv.append(pipe.on_receive)
        return rv

    def _flow_send(self):
        rv = []
        for pipe in reversed(self.pipes):
            if 'on_send' not in pipe._pipeline_all_methods_:
                continue
            rv.append(pipe.on_send)
        return rv


class MetaPipe(type):
    _pipeline_methods_ = {
        'open', 'open_request', 'open_ws',
        'close', 'close_request', 'close_ws',
        'pipe', 'pipe_request', 'pipe_ws',
        'on_pipe_success', 'on_pipe_failure',
        'on_receive', 'on_send'
    }

    def __new__(cls, name, bases, attrs):
        new_class = type.__new__(cls, name, bases, attrs)
        if not bases:
            return new_class
        declared_methods = cls._pipeline_methods_ & set(attrs.keys())
        new_class._pipeline_declared_methods_ = declared_methods
        all_methods = set()
        for base in reversed(new_class.__mro__[:-2]):
            if hasattr(base, '_pipeline_declared_methods_'):
                all_methods = all_methods | base._pipeline_declared_methods_
        all_methods = all_methods | declared_methods
        new_class._pipeline_all_methods_ = all_methods
        new_class._is_flow_request_responsible = bool(
            all_methods & {
                'pipe', 'pipe_request', 'on_pipe_success', 'on_pipe_failure'
            }
        )
        new_class._is_flow_ws_responsible = bool(
            all_methods & {
                'pipe', 'pipe_ws', 'on_pipe_success', 'on_pipe_failure'
            }
        )
        if all_methods.issuperset({'pipe', 'pipe_request'}):
            raise RuntimeError(
                f'{name} has double pipe methods. '
                'Use `pipe` or `pipe_request`, not both.'
            )
        if all_methods.issuperset({'pipe', 'pipe_ws'}):
            raise RuntimeError(
                f'{name} has double pipe methods. '
                'Use `pipe` or `pipe_ws`, not both.'
            )
        return new_class


class Pipe(metaclass=MetaPipe):
    output: Optional[str] = None

    async def open(self):
        pass

    async def open_request(self):
        pass

    async def open_ws(self):
        pass

    async def close(self):
        pass

    async def close_request(self):
        pass

    async def close_ws(self):
        pass

    async def pipe(self, next_pipe, **kwargs):
        return await next_pipe(**kwargs)

    async def pipe_request(self, next_pipe, **kwargs):
        return await next_pipe(**kwargs)

    async def pipe_ws(self, next_pipe, **kwargs):
        return await next_pipe(**kwargs)

    async def on_pipe_success(self):
        pass

    async def on_pipe_failure(self):
        pass

    def on_receive(self, data):
        return data

    def on_send(self, data):
        return data


class RequirePipe(Pipe):
    def __init__(self, condition=None, otherwise=None):
        if condition is None or otherwise is None:
            raise SyntaxError('usage: @requires(condition, otherwise)')
        if not callable(otherwise) and not isinstance(otherwise, str):
            raise SyntaxError("'otherwise' param must be string or callable")
        self.condition = condition
        self.otherwise = otherwise

    async def pipe_request(self, next_pipe, **kwargs):
        flag = self.condition()
        if not flag:
            if self.otherwise is not None:
                if callable(self.otherwise):
                    return self.otherwise()
                redirect(self.otherwise)
            else:
                flash('Insufficient privileges')
                redirect('/')
        return await next_pipe(**kwargs)

    async def pipe_ws(self, next_pipe, **kwargs):
        flag = self.condition()
        if not flag:
            return
        await next_pipe(**kwargs)


class Injector(Pipe):
    namespace: str = '__global__'

    def __init__(self):
        self._injections_ = {}
        if self.namespace != '__global__':
            self._inject = self._inject_local
            return
        self._inject = self._inject_global
        for attr_name in (
            set(dir(self)) -
            self.__class__._pipeline_methods_ -
            {'output', 'namespace'}
        ):
            if attr_name.startswith('_'):
                continue
            attr = getattr(self, attr_name)
            if isinstance(attr, types.MethodType):
                self._injections_[attr_name] = self._wrapped_method(attr)
                continue
            self._injections_[attr_name] = attr

    @staticmethod
    def _wrapped_method(method):
        def wrap(*args, **kwargs):
            return method(*args, **kwargs)
        return wrap

    def _inject_local(self, ctx):
        ctx[self.namespace] = self

    def _inject_global(self, ctx):
        ctx.update(self._injections_)

    async def pipe_request(self, next_pipe, **kwargs):
        ctx = await next_pipe(**kwargs)
        if isinstance(ctx, dict):
            self._inject(ctx)
        return ctx


def _wrap_flow_request_complete(pipe_method, on_success, on_failure, f):
    @wraps(f)
    async def flow(**kwargs):
        try:
            output = await pipe_method(f, **kwargs)
            await on_success()
            return output
        except HTTPResponse:
            await on_success()
            raise
        except Exception:
            await on_failure()
            raise
    return flow


def _wrap_flow_request_success(pipe_method, on_success, on_failure, f):
    @wraps(f)
    async def flow(**kwargs):
        try:
            output = await pipe_method(f, **kwargs)
            await on_success()
            return output
        except HTTPResponse:
            await on_success()
            raise
    return flow


def _wrap_flow_request_failure(pipe_method, on_success, on_failure, f):
    @wraps(f)
    async def flow(**kwargs):
        try:
            return await pipe_method(f, **kwargs)
        except HTTPResponse:
            raise
        except Exception:
            await on_failure()
            raise
    return flow


def _wrap_flow_request_basic(pipe_method, on_success, on_failure, f):
    @wraps(f)
    async def flow(**kwargs):
        return await pipe_method(f, **kwargs)
    return flow


def _wrap_flow_ws_complete(pipe_method, on_success, on_failure, f):
    @wraps(f)
    async def flow(**kwargs):
        try:
            await pipe_method(f, **kwargs)
            await on_success()
        except Exception:
            await on_failure()
            raise
    return flow


def _wrap_flow_ws_success(pipe_method, on_success, on_failure, f):
    @wraps(f)
    async def flow(**kwargs):
        await pipe_method(f, **kwargs)
        await on_success()
    return flow


def _wrap_flow_ws_failure(pipe_method, on_success, on_failure, f):
    @wraps(f)
    async def flow(**kwargs):
        try:
            await pipe_method(f, **kwargs)
        except Exception:
            await on_failure()
            raise
    return flow


def _wrap_flow_ws_basic(pipe_method, on_success, on_failure, f):
    @wraps(f)
    async def flow(**kwargs):
        return await pipe_method(f, **kwargs)
    return flow
