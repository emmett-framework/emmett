# -*- coding: utf-8 -*-
"""
emmett.routing.rules
--------------------

Provides routing rules definition apis.

:copyright: 2014 Giovanni Barillari
:license: BSD-3-Clause
"""

from __future__ import annotations

import os
from typing import Any, Callable

from emmett_core.routing.rules import HTTPRoutingRule as _HTTPRoutingRule

from ..ctx import current
from .routes import HTTPRoute


class HTTPRoutingRule(_HTTPRoutingRule):
    __slots__ = ["injectors", "template_folder", "template_path", "template"]
    current = current
    route_cls = HTTPRoute

    def __init__(
        self,
        router,
        paths=None,
        name=None,
        template=None,
        pipeline=None,
        injectors=None,
        schemes=None,
        hostname=None,
        methods=None,
        prefix=None,
        template_folder=None,
        template_path=None,
        cache=None,
        output="auto",
    ):
        super().__init__(
            router,
            paths=paths,
            name=name,
            pipeline=pipeline,
            schemes=schemes,
            hostname=hostname,
            methods=methods,
            prefix=prefix,
            cache=cache,
            output=output,
        )
        self.template = template
        self.template_folder = template_folder
        self.template_path = template_path or self.app.template_path
        self.pipeline = self.pipeline + self.router.injectors + (injectors or [])

    def _make_builders(self, output_type):
        builder_cls = self.router._outputs[output_type]
        return builder_cls(self), self.router._outputs["empty"](self)

    def __call__(self, f: Callable[..., Any]) -> Callable[..., Any]:
        if not self.template:
            self.template = f.__name__ + self.app.template_default_extension
        if self.template_folder:
            self.template = os.path.join(self.template_folder, self.template)
        return super().__call__(f)
