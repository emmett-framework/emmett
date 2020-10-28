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

from ..cache import RouteCacheRule
from ..pipeline import RequestPipeline, WebsocketPipeline, Pipe
from .routes import HTTPRoute, WebsocketRoute


class RoutingRule:
    __slots__ = ['router']

    def __init__(self, router, *args, **kwargs):
        self.router = router

    @property
    def app(self):
        return self.router.app

    def build_name(self, f):
        filename = os.path.realpath(f.__code__.co_filename)
        short = filename[1 + len(self.app.root_path):].rsplit('.', 1)[0]
        if not short:
            short = filename.rsplit('.', 1)[0]
        if short == "__init__":
            short = self.app.root_path.rsplit('/', 1)[-1]
        #: allow only one naming level if name is not provided
        if len(short.split(os.sep)) > 1:
            short = short.split(os.sep)[-1]
        return '.'.join(short.split(os.sep) + [f.__name__])

    def __call__(self, f: Callable[..., Any]) -> Callable[..., Any]:
        raise NotImplementedError


class HTTPRoutingRule(RoutingRule):
    __slots__ = [
        'cache_rule',
        'f',
        'head_builder',
        'hostname',
        'methods',
        'name',
        'output_type',
        'paths',
        'pipeline_flow_close',
        'pipeline_flow_open',
        'pipeline',
        'prefix',
        'response_builder',
        'schemes',
        'template_folder',
        'template_path',
        'template'
    ]

    def __init__(
        self, router, paths=None, name=None, template=None, pipeline=None,
        injectors=None, schemes=None, hostname=None, methods=None, prefix=None,
        template_folder=None, template_path=None, cache=None, output='auto'
    ):
        super().__init__(router)
        self.name = name
        self.paths = paths
        if self.paths is None:
            self.paths = []
        if not isinstance(self.paths, (list, tuple)):
            self.paths = (self.paths,)
        self.schemes = schemes or ('http', 'https')
        if not isinstance(self.schemes, (list, tuple)):
            self.schemes = (self.schemes,)
        self.methods = methods or ('get', 'post', 'head')
        if not isinstance(self.methods, (list, tuple)):
            self.methods = (self.methods,)
        self.hostname = hostname or self.app.config.hostname_default
        if prefix:
            if not prefix.startswith('/'):
                prefix = '/' + prefix
        self.prefix = prefix
        if output not in self.router._outputs:
            raise SyntaxError(
                'Invalid output specified. Allowed values are: {}'.format(
                    ', '.join(self.router._outputs.keys())))
        self.output_type = output
        self.template = template
        self.template_folder = template_folder
        self.template_path = template_path or self.app.template_path
        self.pipeline = (
            self.router.pipeline + (pipeline or []) +
            self.router.injectors + (injectors or []))
        self.cache_rule = None
        if cache:
            if not isinstance(cache, RouteCacheRule):
                raise RuntimeError(
                    'route cache argument should be a valid caching rule')
            if any(key in self.methods for key in ['get', 'head']):
                self.cache_rule = cache
        # check pipes are indeed valid pipes
        if any(not isinstance(pipe, Pipe) for pipe in self.pipeline):
            raise RuntimeError('Invalid pipeline')

    def _make_builders(self, output_type):
        builder_cls = self.router._outputs[output_type]
        return builder_cls(self), self.router._outputs['empty'](self)

    def __call__(self, f: Callable[..., Any]) -> Callable[..., Any]:
        if not self.paths:
            self.paths.append("/" + f.__name__)
        if not self.name:
            self.name = self.build_name(f)
        # is it good?
        if self.name.endswith("."):
            self.name = self.name + f.__name__
        #
        if not self.template:
            self.template = f.__name__ + self.app.template_default_extension
        if self.template_folder:
            self.template = os.path.join(self.template_folder, self.template)
        pipeline_obj = RequestPipeline(self.pipeline)
        wrapped_f = pipeline_obj(f)
        self.pipeline_flow_open = pipeline_obj._flow_open()
        self.pipeline_flow_close = pipeline_obj._flow_close()
        self.f = wrapped_f
        output_type = pipeline_obj._output_type() or self.output_type
        self.response_builder, self.head_builder = self._make_builders(output_type)
        for idx, path in enumerate(self.paths):
            self.router.add_route(HTTPRoute(self, path, idx))
        return f


class WebsocketRoutingRule(RoutingRule):
    __slots__ = [
        'f',
        'hostname',
        'name',
        'paths',
        'pipeline_flow_close',
        'pipeline_flow_open',
        'pipeline_flow_receive',
        'pipeline_flow_send',
        'pipeline',
        'prefix',
        'schemes'
    ]

    def __init__(
        self, router, paths=None, name=None, pipeline=None, schemes=None,
        hostname=None, prefix=None
    ):
        super().__init__(router)
        self.name = name
        self.paths = paths
        if self.paths is None:
            self.paths = []
        if not isinstance(self.paths, (list, tuple)):
            self.paths = (self.paths,)
        self.schemes = schemes or ('ws', 'wss')
        if not isinstance(self.schemes, (list, tuple)):
            self.schemes = (self.schemes,)
        self.hostname = hostname or self.app.config.hostname_default
        if prefix:
            if not prefix.startswith('/'):
                prefix = '/' + prefix
        self.prefix = prefix
        self.pipeline = self.router.pipeline + (pipeline or [])
        # check pipes are indeed valid pipes
        if any(not isinstance(pipe, Pipe) for pipe in self.pipeline):
            raise RuntimeError('Invalid pipeline')

    def __call__(self, f: Callable[..., Any]) -> Callable[..., Any]:
        if not self.paths:
            self.paths.append("/" + f.__name__)
        if not self.name:
            self.name = self.build_name(f)
        # is it good?
        if self.name.endswith("."):
            self.name = self.name + f.__name__
        #
        pipeline_obj = WebsocketPipeline(self.pipeline)
        wrapped_f = pipeline_obj(f)
        self.pipeline_flow_open = pipeline_obj._flow_open()
        self.pipeline_flow_close = pipeline_obj._flow_close()
        self.pipeline_flow_receive = pipeline_obj._flow_receive()
        self.pipeline_flow_send = pipeline_obj._flow_send()
        self.f = wrapped_f
        for idx, path in enumerate(self.paths):
            self.router.add_route(WebsocketRoute(self, path, idx))
        return f
