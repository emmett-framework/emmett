# -*- coding: utf-8 -*-
"""
    weppy.tools.service
    -------------------

    Provides the services handler.

    :copyright: (c) 2014 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

from ..handlers import Handler
from ..globals import response
from ..serializers import json, xml


class ServiceHandler(Handler):
    def __init__(self, procedure):
        self.procedure = procedure

    def json(self, f, **kwargs):
        response.headers['Content-Type'] = 'application/json; charset=utf-8'
        data = f(**kwargs)
        return json(data)

    def xml(self, f, **kwargs):
        response.headers['Content-Type'] = 'text/xml'
        data = f(**kwargs)
        return xml(data)

    def wrap_call(self, func):
        def wrap(**kwargs):
            if hasattr(self, self.procedure):
                return self.__getattribute__(self.procedure)(func, **kwargs)
            else:
                raise RuntimeError(
                    'weppy cannot handle the service you requested: %s' %
                    self.procedure
                )
        return wrap
