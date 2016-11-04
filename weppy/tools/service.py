# -*- coding: utf-8 -*-
"""
    weppy.tools.service
    -------------------

    Provides the services handler.

    :copyright: (c) 2014 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

from .._internal import warn_of_deprecation
from ..globals import response
from ..pipeline import Pipe
from ..serializers import json, xml


class ServicePipe(Pipe):
    def __init__(self, procedure):
        if not hasattr(self, procedure):
            raise RuntimeError(
                'weppy cannot handle the service you requested: %s' %
                procedure
            )
        self.procedure = getattr(self, procedure)

    def json(self, f, **kwargs):
        response.headers['Content-Type'] = 'application/json; charset=utf-8'
        data = f(**kwargs)
        return json(data)

    def xml(self, f, **kwargs):
        response.headers['Content-Type'] = 'text/xml'
        data = f(**kwargs)
        return xml(data)

    def pipe(self, next_pipe, **kwargs):
        return self.procedure(next_pipe, **kwargs)


class ServiceHandler(ServicePipe):
    def __init__(self, *args, **kwargs):
        warn_of_deprecation('ServiceHandler', 'ServicePipe', stack=3)
        super(ServiceHandler, self).__init__(*args, **kwargs)
