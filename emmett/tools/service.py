# -*- coding: utf-8 -*-
"""
    emmett.tools.service
    --------------------

    Provides the services handler.

    :copyright: (c) 2014-2019 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

from ..ctx import response
from ..pipeline import Pipe
from ..serializers import Serializers


class ServicePipe(Pipe):
    output = 'str'

    def __init__(self, procedure):
        if not hasattr(self, procedure):
            raise RuntimeError(
                'Emmett cannot handle the service you requested: %s' %
                procedure
            )
        self.procedure = getattr(self, procedure)
        self.json_encoder = Serializers.get_for('json')
        self.xml_encoder = Serializers.get_for('xml')

    async def json(self, next_pipe, kwargs):
        response.headers['Content-Type'] = 'application/json; charset=utf-8'
        return self.json_encoder(await next_pipe(**kwargs))

    async def xml(self, next_pipe, kwargs):
        response.headers['Content-Type'] = 'text/xml'
        return self.xml_encoder(await next_pipe(**kwargs))

    def pipe(self, next_pipe, **kwargs):
        return self.procedure(next_pipe, kwargs)
