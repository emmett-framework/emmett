"""
    weppy.pipeline
    --------------

    Provides the pipeline classes.

    :copyright: (c) 2014-2016 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

from functools import wraps
from ._compat import basestring
from .http import HTTP


class Pipeline(object):
    def __init__(self, pipes=[]):
        self.pipes = pipes

    def __call__(self, f):
        def wrap(f, pipe):
            @wraps(f)
            def pipe_flow(**kwargs):
                try:
                    output = pipe.pipe(pipe._wrapped_, **kwargs)
                    pipe.on_pipe_success()
                    return output
                except HTTP:
                    pipe.on_pipe_success()
                    raise
                except:
                    pipe.on_pipe_failure()
                    raise
            pipe._pipe_to_(f)
            return pipe_flow
        for pipe in reversed(self.pipes):
            if isinstance(pipe, Pipe):
                f = wrap(f, pipe)
        return f


class Pipe(object):
    def _pipe_to_(self, f):
        self._wrapped_ = f

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
            from .http import redirect
            if self.otherwise is not None:
                if callable(self.otherwise):
                    return self.otherwise()
                redirect(self.otherwise)
            else:
                from .helpers import flash
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
