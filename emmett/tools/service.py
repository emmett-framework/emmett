# -*- coding: utf-8 -*-
"""
emmett.tools.service
--------------------

Provides the services handler.

:copyright: 2014 Giovanni Barillari
:license: BSD-3-Clause
"""

from emmett_core.pipeline.extras import JSONPipe

from ..ctx import current
from ..pipeline import Pipe
from ..serializers import Serializers


class JSONServicePipe(JSONPipe):
    __slots__ = []
    _current = current


class XMLServicePipe(Pipe):
    __slots__ = ["encoder"]
    output = "str"

    def __init__(self):
        self.encoder = Serializers.get_for("xml")

    async def pipe_request(self, next_pipe, **kwargs):
        current.response.headers._data["content-type"] = "text/xml"
        return self.encoder(await next_pipe(**kwargs))

    def on_send(self, data):
        return self.encoder(data)


def ServicePipe(procedure: str) -> Pipe:
    pipe_cls = {"json": JSONServicePipe, "xml": XMLServicePipe}.get(procedure)
    if not pipe_cls:
        raise RuntimeError("Emmett cannot handle the service you requested: %s" % procedure)
    return pipe_cls()
