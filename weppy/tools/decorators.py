# -*- coding: utf-8 -*-
"""
    weppy.tools.decorators
    ----------------------

    Provides requires and service decorators.

    :copyright: (c) 2014 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

from .._compat import basestring
from ..expose import Expose


class Decorator(object):
    def handler(self):
        pass

    def __call__(self, func):
        obj = Expose.exposing()
        obj.handlers.append(self.handler())
        return func


class requires(Decorator):
    def __init__(self, condition=None, otherwise=None):
        if condition is None or otherwise is None:
            raise SyntaxError(
                'requires usage: @requires(condition, otherwise)'
            )
        if not callable(otherwise) and not isinstance(otherwise, basestring):
            raise SyntaxError(
                "requires 'otherwise' param must be string or callable"
            )
        self.condition = condition
        self.otherwise = otherwise

    def handler(self):
        from ..handlers import RequireHandler
        return RequireHandler(self.condition, self.otherwise)


class service(Decorator):
    def __init__(self, procedure):
        self.procedure = procedure

    @staticmethod
    def json(f):
        return service('json')(f)

    @staticmethod
    def xml(f):
        return service('xml')(f)

    def handler(self):
        from .service import ServiceHandler
        return ServiceHandler(self.procedure)
