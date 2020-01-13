# -*- coding: utf-8 -*-
"""
    emmett.tools.decorators
    -----------------------

    Provides requires and service decorators.

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

from ..routing.router import Router


class Decorator(object):
    def build_pipe(self):
        pass

    def __call__(self, func):
        obj = Router.exposing()
        obj.pipeline.append(self.build_pipe())
        return func


class requires(Decorator):
    def __init__(self, condition=None, otherwise=None):
        if condition is None or otherwise is None:
            raise SyntaxError(
                'requires usage: @requires(condition, otherwise)'
            )
        if not callable(otherwise) and not isinstance(otherwise, str):
            raise SyntaxError(
                "requires 'otherwise' param must be string or callable"
            )
        self.condition = condition
        self.otherwise = otherwise

    def build_pipe(self):
        from ..pipeline import RequirePipe
        return RequirePipe(self.condition, self.otherwise)


class service(Decorator):
    def __init__(self, procedure):
        self.procedure = procedure

    @staticmethod
    def json(f):
        return service('json')(f)

    @staticmethod
    def xml(f):
        return service('xml')(f)

    def build_pipe(self):
        from .service import ServicePipe
        return ServicePipe(self.procedure)
