# -*- coding: utf-8 -*-
"""
    emmett.routing.router
    ---------------------

    Provides router implementations.

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

import re

from ..ctx import current
from ..http import HTTP
from .response import (
    AutoResponseBuilder, BytesResponseBuilder, ResponseBuilder,
    TemplateResponseBuilder)
from .rules import HTTPRoutingRule, WebsocketRoutingRule


class Router:
    __slots__ = [
        'app', 'routes_in', 'routes_out', '_routes_str', '_routes_nohost',
        '_get_routes_in_for_host', '_prefix_main', '_prefix_main_len',
        '_match_lang'
    ]

    _outputs = {}
    _routing_rule_cls = None
    _routing_signal = 'before_routes'
    _routing_started = False
    _routing_stack = []
    _re_components = re.compile(r'(\()?([^<\w]+)?<(\w+)\:(\w+)>(\)\?)?')

    def __init__(self, app, url_prefix=None):
        self.app = app
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
            for idx, el in enumerate(params):
                components.append(params[idx] + statics[idx + 1])
        return components

    def _get_routes_in_for_host_match(self, wrapper):
        return (
            self.routes_in.get(wrapper.host, self.routes_in['__any__']),
            self.routes_in['__any__'])

    def _get_routes_in_for_host_nomatch(self, wrapper):
        return self._routes_nohost

    def _match_with_lang(self, request, path):
        path, lang = self._split_lang(path)
        current.language = request.language = lang
        return path

    def _match_no_lang(self, request, path):
        request.language = None
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
    _outputs = {
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
                'GET', 'HEAD', 'POST', 'PUT', 'DELETE', 'OPTIONS', 'PATCH'
            ]:
                rv[scheme][method] = {'static': {}, 'match': {}}
        return rv

    def add_route_str(self, route):
        self._routes_str[route.name] = "%s %s://%s%s%s -> %s" % (
            "|".join(route.methods).upper(),
            "|".join(route.schemes),
            route.hostname or "<any>",
            self._prefix_main,
            route.path,
            route.name
        )

    def add_route(self, route):
        host = route.hostname or '__any__'
        if host not in self.routes_in:
            self.routes_in[host] = self._build_routing_dict()
            self._get_routes_in_for_host = self._get_routes_in_for_host_match
        for scheme in route.schemes:
            for method in route.methods:
                routing_dict = self.routes_in[host][scheme][method.upper()]
                if route.is_static:
                    routing_dict['static'][route.path] = route
                else:
                    routing_dict['match'][route.name] = route
        self.routes_out[route.name] = {
            'host': route.hostname,
            'path': self.build_route_components(route.path)
        }
        self.add_route_str(route)

    def match(self, request):
        path = self.remove_trailslash(request.path)
        path = self._match_lang(request, path)
        for routing_dict in self._get_routes_in_for_host(request):
            sub_dict = routing_dict[request.scheme][request.method]
            route = sub_dict['static'].get(path)
            if route:
                return route, {}
            for route in sub_dict['match'].values():
                match, args = route.match(path)
                if match:
                    return route, args
        return None, {}

    async def dispatch(self):
        request, response = current.request, current.response
        route, reqargs = self.match(request)
        if not route:
            raise HTTP(404, body="Resource not found\n")
        request.name = route.name
        http_cls, output = await route.dispatcher.dispatch(request, reqargs)
        return http_cls(
            response.status, output, response.headers, response.cookies)


class WebsocketRouter(Router):
    __slots__ = ['pipeline']

    _routing_rule_cls = WebsocketRoutingRule

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
        host = route.hostname or '__any__'
        if host not in self.routes_in:
            self.routes_in[host] = self._build_routing_dict()
            self._get_routes_in_for_host = self._get_routes_in_for_host_match
        for scheme in route.schemes:
            routing_dict = self.routes_in[host][scheme]
            if route.is_static:
                routing_dict['static'][route.path] = route
            else:
                routing_dict['match'][route.name] = route
        self.routes_out[route.name] = {
            'host': route.hostname,
            'path': self.build_route_components(route.path)
        }
        self.add_route_str(route)

    def match(self, websocket):
        path = self.remove_trailslash(websocket.path)
        path = self._match_lang(websocket, path)
        for routing_dict in self._get_routes_in_for_host(websocket):
            sub_dict = routing_dict[websocket.scheme]
            route = sub_dict['static'].get(path)
            if route:
                return route, {}
            for route in sub_dict['match'].values():
                match, args = route.match(path)
                if match:
                    return route, args
        return None, {}

    async def dispatch(self):
        websocket = current.websocket
        route, reqargs = self.match(websocket)
        if not route:
            raise HTTP(404, body="Resource not found\n")
        websocket.name = route.name
        websocket._bind_flow(
            route.pipeline_flow_receive, route.pipeline_flow_send)
        await route.dispatcher.dispatch(websocket, reqargs)


class RoutingCtx:
    __slots__ = ['router', 'rule']

    def __init__(self, router, rule_cls, *args, **kwargs):
        self.router = router
        self.rule = rule_cls(self.router, *args, **kwargs)
        self.router._routing_stack.append(self.rule)

    def __call__(self, f):
        self.router.app.send_signal('before_route', route=self.rule, f=f)
        rv = self.rule(f)
        self.router.app.send_signal('after_route', route=self.rule)
        self.router._routing_stack.pop()
        return rv
