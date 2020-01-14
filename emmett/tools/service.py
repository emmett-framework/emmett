# -*- coding: utf-8 -*-
"""
    emmett.tools.service
    --------------------

    Provides the services handler.

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

from ..ctx import response
from ..parsers import Parsers
from ..pipeline import Pipe
from ..serializers import Serializers


class JSONServicePipe(Pipe):
    __slots__ = ['decoder', 'encoder']
    output = 'str'

    def __init__(self):
        self.decoder = Parsers.get_for('json')
        self.encoder = Serializers.get_for('json')

    async def pipe_request(self, next_pipe, **kwargs):
        response.headers['Content-Type'] = 'application/json; charset=utf-8'
        return self.encoder(await next_pipe(**kwargs))

    def receive(self, data):
        return self.decoder(data)

    def send(self, data):
        return self.encoder(data)


class XMLServicePipe(Pipe):
    __slots__ = ['encoder']
    output = 'str'

    def __init__(self):
        self.encoder = Serializers.get_for('xml')

    async def pipe_request(self, next_pipe, **kwargs):
        response.headers['Content-Type'] = 'text/xml'
        return self.encoder(await next_pipe(**kwargs))

    def send(self, data):
        return self.encoder(data)


def ServicePipe(procedure: str) -> Pipe:
    pipe_cls = {
        'json': JSONServicePipe,
        'xml': XMLServicePipe
    }.get(procedure)
    if not pipe_cls:
        raise RuntimeError(
            'Emmett cannot handle the service you requested: %s' %
            procedure
        )
    return pipe_cls()
