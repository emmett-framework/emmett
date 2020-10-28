# -*- coding: utf-8 -*-
"""
    emmett.routing.router
    ---------------------

    Provides router implementations.

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

from __future__ import annotations

import re

from collections import namedtuple
from typing import Any, Callable, Dict, List, Type

from ..ctx import current
from ..extensions import Signals
from ..http import HTTP
from .response import (
    MetaResponseBuilder,
    EmptyResponseBuilder,
    ResponseBuilder,
    AutoResponseBuilder,
    BytesResponseBuilder,
    TemplateResponseBuilder
)
from .rules import RoutingRule, HTTPRoutingRule, WebsocketRoutingRule


RouteRecReq = namedtuple(
    "RouteRecReq", ["name", "match", "dispatch"]
)
RouteRecWS = namedtuple(
    "RouteRecWS", ["name", "match", "dispatch", "flow_recv", "flow_send"]
)


class Router:
    __slots__ = [
        '_get_routes_in_for_host',
        '_match_lang',
        '_prefix_main_len',
        '_prefix_main',
        '_routes_nohost',
        '_routes_str',
        'app',
        'routes_in',
        'routes_out',
        'routes'
    ]

    _outputs: Dict[str, Type[MetaResponseBuilder]] = {}
    _routing_rule_cls: Type[RoutingRule] = RoutingRule
    _routing_signal = Signals.before_routes
    _routing_started = False
    _routing_stack: List[RoutingRule] = []
    _re_components = re.compile(r'(\()?([^<\w]+)?<(\w+)\:(\w+)>(\)\?)?')

    def __init__(self, app, url_prefix=None):
        self.app = app
        self.routes = []
        self.routes_in = {'__any__': self._build_routing_dict()}
        self.routes_out = {}
        self._routes_str = {}
        self._routes_nohost = (self.routes_in['__any__'], )
        self._get_routes_in_for_host = self._get_routes_in_for_host_nomatch
        main_prefix = url_prefix or ''
        if main_prefix:
            main_prefix = main_prefix.rstrip('/')
            if not main_prefix.startswith('/'):
                main_prefix = '/' + main_prefix
            if main_prefix == '/':
                main_prefix = ''
        self._prefix_main = main_prefix
        self._prefix_main_len = len(self._prefix_main)
        self._set_language_handling()

    def _set_language_handling(self):
        self._match_lang = (
            self._match_with_lang if self.app.language_force_on_url
            else self._match_no_lang)

    @property
    def static_versioning(self):
        return (
            self.app.config.static_version_urls and
            self.app.config.static_version
        ) or ''

    @staticmethod
    def _build_routing_dict():
        return {'static': {}, 'match': {}}

    @classmethod
    def build_route_components(cls, path):
        components = []
        params = []
        for match in cls._re_components.findall(path):
            params.append(match[1] + "{}")
        statics = cls._re_components.sub("{}", path).split("{}")
        if not params:
            components = statics
        else:
            components.append(statics[0])
            for idx, _ in enumerate(params):
                components.append(params[idx] + statics[idx + 1])
        return components

    def _get_routes_in_for_host_match(self, wrapper):
        return (
            self.routes_in.get(wrapper.host, self.routes_in['__any__']),
            self.routes_in['__any__'])

    def _get_routes_in_for_host_nomatch(self, wrapper):
        return self._routes_nohost

    def _match_with_lang(self, wrapper, path):
        path, lang = self._split_lang(path)
        current.language = wrapper.language = lang
        return path

    def _match_no_lang(self, wrapper, path):
        wrapper.language = None
        return path

    @staticmethod
    def remove_trailslash(path):
        return path.rstrip('/') or path

    def _split_lang(self, path):
        default = self.app.language_default
        if len(path) <= 1:
            return path, default
        clean_path = path.lstrip('/')
        if clean_path[2:3] == '/':
            lang, new_path = clean_path[:2], clean_path[2:]
            if lang != default and lang in self.app._languages_set:
                return new_path, lang
        return path, default

    def add_route(self, route):
        raise NotImplementedError

    def match(self, wrapper):
        raise NotImplementedError

    async def dispatch(self):
        raise NotImplementedError

    def __call__(self, *args, **kwargs):
        if not self.__class__._routing_started:
            self.__class__._routing_started = True
            self.app.send_signal(self._routing_signal)
        return RoutingCtx(self, self._routing_rule_cls, *args, **kwargs)

    @classmethod
    def exposing(cls):
        return cls._routing_stack[-1]


class HTTPRouter(Router):
    __slots__ = ['pipeline', 'injectors']

    _routing_rule_cls = HTTPRoutingRule
    _routing_rec_builder = RouteRecReq

    _outputs = {
        'empty': EmptyResponseBuilder,
        'auto': AutoResponseBuilder,
        'bytes': BytesResponseBuilder,
        'str': ResponseBuilder,
        'template': TemplateResponseBuilder
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pipeline = []
        self.injectors = []

    @staticmethod
    def _build_routing_dict():
        rv = {}
        for scheme in ['http', 'https']:
            rv[scheme] = {}
            for method in [
                'DELETE', 'GET', 'HEAD', 'OPTIONS', 'PATCH', 'POST', 'PUT'
            ]:
                rv[scheme][method] = {'static': {}, 'match': {}}
        return rv

    def add_route_str(self, route):
        self._routes_str[route.name] = "%s %s://%s%s%s -> %s" % (
            "|".join(route.methods),
            "|".join(route.schemes),
            route.hostname or "<any>",
            self._prefix_main,
            route.path,
            route.name
        )

    def add_route(self, route):
        self.routes.append(route)
        host = route.hostname or '__any__'
        if host not in self.routes_in:
            self.routes_in[host] = self._build_routing_dict()
            self._get_routes_in_for_host = self._get_routes_in_for_host_match
        for scheme in route.schemes:
            for method in route.methods:
                routing_dict = self.routes_in[host][scheme][method]
                slot, key = (
                    ('static', route.path) if route.is_static else
                    ('match', route.name)
                )
                routing_dict[slot][key] = self._routing_rec_builder(
                    name=route.name,
                    match=route.match,
                    dispatch=route.dispatchers[method].dispatch
                )
        self.routes_out[route.name] = {
            'host': route.hostname,
            'path': self.build_route_components(route.path)
        }
        self.add_route_str(route)

    def match(self, request):
        path = self._match_lang(
            request,
            self.remove_trailslash(request.path)
        )
        for routing_dict in self._get_routes_in_for_host(request):
            sub_dict = routing_dict[request.scheme][request.method]
            element = sub_dict['static'].get(path)
            if element:
                return element, {}
            for element in sub_dict['match'].values():
                match, args = element.match(path)
                if match:
                    return element, args
        return None, {}

    async def dispatch(self, request, response):
        match, reqargs = self.match(request)
        if not match:
            raise HTTP(404, body="Resource not found\n")
        request.name = match.name
        return await match.dispatch(reqargs, response)


class WebsocketRouter(Router):
    __slots__ = ['pipeline']

    _routing_rule_cls = WebsocketRoutingRule
    _routing_rec_builder = RouteRecWS

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pipeline = []

    @staticmethod
    def _build_routing_dict():
        rv = {}
        for scheme in ['ws', 'wss']:
            rv[scheme] = {'static': {}, 'match': {}}
        return rv

    def add_route_str(self, route):
        self._routes_str[route.name] = "%s://%s%s%s -> %s" % (
            "|".join(route.schemes),
            route.hostname or "<any>",
            self._prefix_main,
            route.path,
            route.name
        )

    def add_route(self, route):
        self.routes.append(route)
        host = route.hostname or '__any__'
        if host not in self.routes_in:
            self.routes_in[host] = self._build_routing_dict()
            self._get_routes_in_for_host = self._get_routes_in_for_host_match
        for scheme in route.schemes:
            routing_dict = self.routes_in[host][scheme]
            slot, key = (
                ('static', route.path) if route.is_static else
                ('match', route.name)
            )
            routing_dict[slot][key] = self._routing_rec_builder(
                name=route.name,
                match=route.match,
                dispatch=route.dispatcher.dispatch,
                flow_recv=route.pipeline_flow_receive,
                flow_send=route.pipeline_flow_send
            )
        self.routes_out[route.name] = {
            'host': route.hostname,
            'path': self.build_route_components(route.path)
        }
        self.add_route_str(route)

    def match(self, websocket):
        path = self._match_lang(
            websocket,
            self.remove_trailslash(websocket.path)
        )
        for routing_dict in self._get_routes_in_for_host(websocket):
            sub_dict = routing_dict[websocket.scheme]
            element = sub_dict['static'].get(path)
            if element:
                return element, {}
            for element in sub_dict['match'].values():
                match, args = element.match(path)
                if match:
                    return element, args
        return None, {}

    async def dispatch(self, websocket):
        match, reqargs = self.match(websocket)
        if not match:
            raise HTTP(404, body="Resource not found\n")
        websocket.name = match.name
        websocket._bind_flow(
            match.flow_recv,
            match.flow_send
        )
        await match.dispatch(reqargs)


class RoutingCtx:
    __slots__ = ['router', 'rule']

    def __init__(
        self,
        router: Router,
        rule_cls: Type[RoutingRule],
        *args,
        **kwargs
    ):
        self.router = router
        self.rule = rule_cls(self.router, *args, **kwargs)
        self.router._routing_stack.append(self.rule)

    def __call__(self, f: Callable[..., Any]) -> Callable[..., Any]:
        self.router.app.send_signal(Signals.before_route, route=self.rule, f=f)
        rv = self.rule(f)
        self.router.app.send_signal(Signals.after_route, route=self.rule)
        self.router._routing_stack.pop()
        return rv
