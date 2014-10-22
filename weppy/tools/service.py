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
from ..serializers import json


class ServiceHandler(Handler):
    def __init__(self, procedure):
        self.procedure = procedure

    def json(self, f, **kwargs):
        response.headers['Content-Type'] = \
            'application/json; charset=utf-8'
        data = f(**kwargs)
        return json(data)

    def wrap_call(self, func):
        def wrap(**kwargs):
            if self.procedure == "json":
                return self.json(func, **kwargs)
        return wrap
