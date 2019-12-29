"""
    weppy.pipeline
    --------------

    Provides the pipeline classes.

    :copyright: (c) 2014-2018 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

from functools import wraps
from ._compat import basestring, with_metaclass
from .helpers import flash
from .http import HTTP, redirect


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

    def __call__(self, f):
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
            rv.append(pipe)
        return rv

    def _flow_close(self):
        rv = []
        for pipe in reversed(self.pipes):
            if 'close' not in pipe._pipeline_all_methods_:
                continue
            rv.append(pipe)
        return rv


class PipeLink(object):
    def __init__(self, pipe, f):
        self.pipe = pipe
        self.f = f


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


class Pipe(with_metaclass(MetaPipe)):
    def open(self):
        pass

    def pipe(self, next_pipe, **kwargs):
        return next_pipe(**kwargs)

    def on_pipe_success(self):
        pass

    def on_pipe_failure(self):
        pass

    def close(self):
        pass


class RequirePipe(Pipe):
    def __init__(self, condition=None, otherwise=None):
        if condition is None or otherwise is None:
            raise SyntaxError('usage: @requires(condition, otherwise)')
        if not callable(otherwise) and not isinstance(otherwise, basestring):
            raise SyntaxError("'otherwise' param must be string or callable")
        self.condition = condition
        self.otherwise = otherwise

    def pipe(self, next_pipe, **kwargs):
        flag = self.condition()
        if not flag:
            if self.otherwise is not None:
                if callable(self.otherwise):
                    return self.otherwise()
                redirect(self.otherwise)
            else:
                flash('Insufficient privileges')
                redirect('/')
        return next_pipe(**kwargs)


class Injector(Pipe):
    def __init__(self):
        self._injection_attrs_ = []
        for attr in set(dir(self)) - self.__class__._pipeline_methods_:
            if attr.startswith('_'):
                continue
            self._injection_attrs_.append(attr)

    def _inject(self, ctx):
        for attr in self._injection_attrs_:
            ctx[attr] = getattr(self, attr)

    def pipe(self, next_pipe, **kwargs):
        ctx = next_pipe(**kwargs)
        if isinstance(ctx, dict):
            self._inject(ctx)
        return ctx


def _wrap_flow_complete(pipe, f):
    @wraps(f)
    def flow(**kwargs):
        try:
            output = pipe.pipe(f, **kwargs)
            pipe.on_pipe_success()
            return output
        except HTTP:
            pipe.on_pipe_success()
            raise
        except Exception:
            pipe.on_pipe_failure()
            raise
    return flow


def _wrap_flow_success(pipe, f):
    @wraps(f)
    def flow(**kwargs):
        try:
            output = pipe.pipe(f, **kwargs)
            pipe.on_pipe_success()
            return output
        except HTTP:
            pipe.on_pipe_success()
            raise
    return flow


def _wrap_flow_failure(pipe, f):
    @wraps(f)
    def flow(**kwargs):
        try:
            return pipe.pipe(f, **kwargs)
        except HTTP:
            raise
        except Exception:
            pipe.on_pipe_failure()
            raise
    return flow


def _wrap_flow_basic(pipe, f):
    @wraps(f)
    def flow(**kwargs):
        return pipe.pipe(f, **kwargs)
    return flow
