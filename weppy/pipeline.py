"""
    weppy.pipeline
    --------------

    Provides the pipeline classes.

    :copyright: (c) 2014-2018 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

import asyncio

from functools import wraps

from .helpers import flash
from .http import HTTPResponse, redirect


class Pipeline(object):
    def __init__(self, pipes=[]):
        self.pipes = pipes

    def _get_proper_wrapper(self, pipe):
        if pipe._pipeline_all_methods_.issuperset(
            {'on_pipe_success', 'on_pipe_failure'}
        ):
            rv = _wrap_flow_complete
        elif 'on_pipe_success' in pipe._pipeline_all_methods_:
            rv = _wrap_flow_success
        elif 'on_pipe_failure' in pipe._pipeline_all_methods_:
            rv = _wrap_flow_failure
        else:
            rv = _wrap_flow_basic
        return rv

    @staticmethod
    def _awaitable_wrap(f):
        @wraps(f)
        async def awaitable(*args, **kwargs):
            return f(*args, **kwargs)
        return awaitable

    def __call__(self, f):
        if not asyncio.iscoroutinefunction(f):
            f = self._awaitable_wrap(f)
        for pipe in reversed(self.pipes):
            if not isinstance(pipe, Pipe):
                continue
            if not pipe._is_flow_responsible:
                continue
            wrapper = self._get_proper_wrapper(pipe)
            f = wrapper(pipe, f)
        return f

    def _flow_open(self):
        rv = []
        for pipe in self.pipes:
            if 'open' not in pipe._pipeline_all_methods_:
                continue
            rv.append(pipe.open)
        return rv

    def _flow_close(self):
        rv = []
        for pipe in reversed(self.pipes):
            if 'close' not in pipe._pipeline_all_methods_:
                continue
            rv.append(pipe.close)
        return rv

    def _output_type(self):
        rv = None
        for pipe in reversed(self.pipes):
            if not pipe._is_flow_responsible or pipe.output is None:
                continue
            rv = pipe.output
        return rv


class MetaPipe(type):
    _pipeline_methods_ = {
        'open', 'close', 'pipe', 'on_pipe_success', 'on_pipe_failure'
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
        new_class._is_flow_responsible = bool(
            all_methods & {'pipe', 'on_pipe_success', 'on_pipe_failure'})
        return new_class


class Pipe(metaclass=MetaPipe):
    output = None

    async def open(self):
        pass

    async def pipe(self, next_pipe, **kwargs):
        return await next_pipe(**kwargs)

    async def on_pipe_success(self):
        pass

    async def on_pipe_failure(self):
        pass

    async def close(self):
        pass


class RequirePipe(Pipe):
    def __init__(self, condition=None, otherwise=None):
        if condition is None or otherwise is None:
            raise SyntaxError('usage: @requires(condition, otherwise)')
        if not callable(otherwise) and not isinstance(otherwise, str):
            raise SyntaxError("'otherwise' param must be string or callable")
        self.condition = condition
        self.otherwise = otherwise

    async def pipe(self, next_pipe, **kwargs):
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


class Injector(Pipe):
    def __init__(self):
        self._injection_attrs_ = []
        for attr in (
            set(dir(self)) - self._pipeline_all_methods_ - {'output'}
        ):
            if attr.startswith('_'):
                continue
            self._injection_attrs_.append(attr)

    def _inject(self, ctx):
        for attr in self._injection_attrs_:
            ctx[attr] = getattr(self, attr)

    async def pipe(self, next_pipe, **kwargs):
        ctx = await next_pipe(**kwargs)
        if isinstance(ctx, dict):
            self._inject(ctx)
        return ctx


def _wrap_flow_complete(pipe, f):
    @wraps(f)
    async def flow(**kwargs):
        try:
            output = await pipe.pipe(f, **kwargs)
            await pipe.on_pipe_success()
            return output
        except HTTPResponse:
            await pipe.on_pipe_success()
            raise
        except Exception:
            await pipe.on_pipe_failure()
            raise
    return flow


def _wrap_flow_success(pipe, f):
    @wraps(f)
    async def flow(**kwargs):
        try:
            output = await pipe.pipe(f, **kwargs)
            await pipe.on_pipe_success()
            return output
        except HTTPResponse:
            await pipe.on_pipe_success()
            raise
    return flow


def _wrap_flow_failure(pipe, f):
    @wraps(f)
    async def flow(**kwargs):
        try:
            return await pipe.pipe(f, **kwargs)
        except Exception:
            await pipe.on_pipe_failure()
            raise
    return flow


def _wrap_flow_basic(pipe, f):
    @wraps(f)
    async def flow(**kwargs):
        return await pipe.pipe(f, **kwargs)
    return flow
