# -*- coding: utf-8 -*-
"""
emmett.routing.router
---------------------

Provides router implementations.

:copyright: 2014 Giovanni Barillari
:license: BSD-3-Clause
"""

from __future__ import annotations

from emmett_core.routing.router import (
    HTTPRouter as _HTTPRouter,
    RoutingCtx as RoutingCtx,
    RoutingCtxGroup as RoutingCtxGroup,
    WebsocketRouter as WebsocketRouter,
)

from .response import AutoResponseBuilder, SnippetResponseBuilder, TemplateResponseBuilder
from .rules import HTTPRoutingRule


class HTTPRouter(_HTTPRouter):
    __slots__ = ["injectors"]

    _routing_rule_cls = HTTPRoutingRule
    _outputs = {
        **_HTTPRouter._outputs,
        **{
            "auto": AutoResponseBuilder,
            "template": TemplateResponseBuilder,
            "snippet": SnippetResponseBuilder,
        },
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.injectors = []
