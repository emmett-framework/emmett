# -*- coding: utf-8 -*-
"""
    emmett.tools.decorators
    -----------------------

    Provides requires and service decorators.

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

# from ..routing.router import Router
from emmett_core.pipeline.dyn import ServicePipeBuilder as _ServicePipeBuilder, requires as _requires, service as _service

from ..pipeline import RequirePipe
from .service import XMLServicePipe


class ServicePipeBuilder(_ServicePipeBuilder):
    _pipe_cls = {
        **_ServicePipeBuilder._pipe_cls,
        **{"xml": XMLServicePipe}
    }


class requires(_requires):
    _pipe_cls = RequirePipe


class service(_service):
    _inner_builder = ServicePipeBuilder()

    @staticmethod
    def xml(f):
        return service('xml')(f)
