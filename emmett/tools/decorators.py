# -*- coding: utf-8 -*-
"""
emmett.tools.decorators
-----------------------

Provides requires and service decorators.

:copyright: 2014 Giovanni Barillari
:license: BSD-3-Clause
"""

from emmett_core.pipeline.dyn import (
    ServicePipeBuilder as _ServicePipeBuilder,
    requires as _requires,
    service as _service,
    sse as _sse,
    stream as _stream,
)

from ..pipeline import RequirePipe
from .service import JSONServicePipe, XMLServicePipe
from .stream import SSEPipe, StreamPipe


class ServicePipeBuilder(_ServicePipeBuilder):
    _pipe_cls = {"json": JSONServicePipe, "xml": XMLServicePipe}


class requires(_requires):
    _pipe_cls = RequirePipe


class stream(_stream):
    _pipe_cls = StreamPipe


class sse(_sse):
    _pipe_cls = SSEPipe


class service(_service):
    _inner_builder = ServicePipeBuilder()

    @staticmethod
    def xml(f):
        return service("xml")(f)
