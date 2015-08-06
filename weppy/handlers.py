"""
    weppy.handlers
    --------------

    Provide the Handler class and wrapper to process handlers.

    :copyright: (c) 2015 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

from ._compat import basestring
from .http import HTTP


class _wrapWithHandlers(object):
    def __init__(self, handlers=[]):
        self.handlers = handlers

    def __call__(self, f):
        def wrap(f, handler):
            def g(*a, **b):
                try:
                    handler.on_start()
                    output = handler.wrap_call(f)(*a, **b)
                    handler.on_success()
                    return output
                except HTTP:
                    handler.on_success()
                    raise
                else:
                    handler.on_failure()
                    raise
            return g
        for handler in reversed(self.handlers):
            if isinstance(handler, Handler):
                f = wrap(f, handler)
        return f


class Handler(object):
    def on_start(self):
        pass

    def on_success(self):
        pass

    def on_failure(self):
        pass

    def wrap_call(self, func):
        return func

    def on_end(self):
        pass


class RequireHandler(Handler):
    def __init__(self, condition=None, otherwise=None):
        if condition is None or otherwise is None:
            raise SyntaxError('usage: @requires(condition, otherwise)')
        if not callable(otherwise) and not isinstance(otherwise, basestring):
            raise SyntaxError("'otherwise' param must be string or callable")
        self.condition = condition
        self.otherwise = otherwise

    def wrap_call(self, func):
        def wrap(*args, **kwargs):
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
            return func(*args, **kwargs)
        return wrap


class Helper(Handler):
    def _inject(self, d):
        exclude = ['on_start', 'on_end', 'on_success', 'on_failure',
                   'wrap_call']
        attr_list = dir(self)
        for attr in attr_list:
            if attr.startswith('_') or attr in exclude:
                continue
            d[attr] = self.__getattribute__(attr)
        return d

    def wrap_call(self, func):
        def g(*a, **b):
            output = func(*a, **b)
            if isinstance(output, dict):
                output = self._inject(output)
            return output
        return g
