# -*- coding: utf-8 -*-
"""
emmett.pipeline
---------------

Provides the pipeline classes.

:copyright: 2014 Giovanni Barillari
:license: BSD-3-Clause
"""

import types

from emmett_core.http.helpers import redirect
from emmett_core.pipeline.extras import RequirePipe as _RequirePipe
from emmett_core.pipeline.pipe import Pipe as Pipe

from .ctx import current
from .helpers import flash


class RequirePipe(_RequirePipe):
    __slots__ = ["flash"]
    _current = current

    def __init__(self, condition=None, otherwise=None, flash=True):
        super().__init__(condition=condition, otherwise=otherwise)
        self.flash = flash

    async def pipe_request(self, next_pipe, **kwargs):
        flag = self.condition()
        if not flag:
            if self.otherwise is not None:
                if callable(self.otherwise):
                    return self.otherwise()
                redirect(self.__class__._current, self.otherwise)
            else:
                if self.flash:
                    flash("Insufficient privileges")
                redirect(self.__class__._current, "/")
        return await next_pipe(**kwargs)


class Injector(Pipe):
    namespace: str = "__global__"

    def __init__(self):
        self._injections_ = {}
        if self.namespace != "__global__":
            self._inject = self._inject_local
            return
        self._inject = self._inject_global
        for attr_name in set(dir(self)) - self.__class__._pipeline_methods_ - {"output", "namespace"}:
            if attr_name.startswith("_"):
                continue
            attr = getattr(self, attr_name)
            if isinstance(attr, types.MethodType):
                self._injections_[attr_name] = self._wrapped_method(attr)
                continue
            self._injections_[attr_name] = attr

    @staticmethod
    def _wrapped_method(method):
        def wrap(*args, **kwargs):
            return method(*args, **kwargs)

        return wrap

    def _inject_local(self, ctx):
        ctx[self.namespace] = self

    def _inject_global(self, ctx):
        ctx.update(self._injections_)

    async def pipe_request(self, next_pipe, **kwargs):
        ctx = await next_pipe(**kwargs)
        if isinstance(ctx, dict):
            self._inject(ctx)
        return ctx
