"""
    weppy.handlers
    --------------

    Provide the Handler class and wrapper to process handlers.

    :copyright: (c) 2014-2017 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

from ._internal import warn_of_deprecation
from .pipeline import Pipe, RequirePipe, Injector


class Handler(Pipe):
    def __init__(self):
        warn_of_deprecation('Handler', 'Pipe', stack=3)

    def open(self):
        self.on_start()

    def pipe(self, next_pipe, **kwargs):
        return self.wrap_call(next_pipe)(**kwargs)

    def on_pipe_success(self):
        self.on_success()

    def on_pipe_failure(self):
        self.on_failure()

    def close(self):
        self.on_end()

    def on_start(self):
        pass

    def on_success(self):
        pass

    def on_failure(self):
        pass

    def wrap_call(self, f):
        return f

    def on_end(self):
        pass


class RequireHandler(RequirePipe):
    def __init__(self, *args, **kwargs):
        warn_of_deprecation('RequireHandler', 'RequirePipe', stack=3)


class Helper(Injector):
    def __init__(self):
        warn_of_deprecation('Helper', 'Injector', stack=3)
