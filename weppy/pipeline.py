"""
    weppy.pipeline
    --------------

    Provides the pipeline classes.

    :copyright: (c) 2014-2017 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

from functools import wraps
from ._compat import basestring
from .helpers import flash
from .http import HTTP, redirect


class Pipeline(object):
    def __init__(self, pipes=[]):
        self.pipes = pipes

    def __call__(self, f):
        def wrap(link):
            @wraps(link.f)
            def pipe_flow(**kwargs):
                try:
                    output = link.pipe.pipe(link.f, **kwargs)
                    link.pipe.on_pipe_success()
                    return output
                except HTTP:
                    link.pipe.on_pipe_success()
                    raise
                except:
                    link.pipe.on_pipe_failure()
                    raise
            return pipe_flow
        for pipe in reversed(self.pipes):
            if isinstance(pipe, Pipe):
                f = wrap(PipeLink(pipe, f))
        return f


class PipeLink(object):
    def __init__(self, pipe, f):
        self.pipe = pipe
        self.f = f


class Pipe(object):
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
    def _inject(self, ctx):
        exclude = [
            'on_start', 'on_end', 'on_success', 'on_failure', 'pipe']
        attr_list = dir(self)
        for attr in attr_list:
            if attr.startswith('_') or attr in exclude:
                continue
            ctx[attr] = self.__getattribute__(attr)

    def pipe(self, next_pipe, **kwargs):
        ctx = next_pipe(**kwargs)
        if isinstance(ctx, dict):
            self._inject(ctx)
        return ctx
