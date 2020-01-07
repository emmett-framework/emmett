# -*- coding: utf-8 -*-
"""
    emmett.routing.routes
    ---------------------

    Provides routes objects.

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

import pendulum
import re

from functools import wraps

from ..http import HTTP
from .dispatchers import (
    RequestDispatcher, RequestOpenDispatcher,
    RequestCloseDispatcher, RequestFlowDispatcher,
    WSDispatcher, WSOpenDispatcher, WSCloseDispatcher, WSFlowDispatcher,
    CacheDispatcher, CacheOpenDispatcher,
    CacheCloseDispatcher, CacheFlowDispatcher
)

REGEX_INT = re.compile(r'<int\:(\w+)>')
REGEX_STR = re.compile(r'<str\:(\w+)>')
REGEX_ANY = re.compile(r'<any\:(\w+)>')
REGEX_ALPHA = re.compile(r'<alpha\:(\w+)>')
REGEX_DATE = re.compile(r'<date\:(\w+)>')
REGEX_FLOAT = re.compile(r'<float\:(\w+)>')


class Route:
    __slots__ = [
        'name', 'f', 'regex', 'match', 'is_static', 'parse_reqargs',
        'path', 'schemes', 'hostname',
        'pipeline_flow_open', 'pipeline_flow_close',
        'dispatcher'
    ]
    _re_condl = re.compile(r'\(.*\)\?')
    _re_param = re.compile(r'<(\w+)\:(\w+)>')

    def __init__(self, rule, path, idx):
        self.name = rule.name if idx == 0 else f"{rule.name}.{idx}"
        self.f = rule.f
        if not path.startswith('/'):
            path = '/' + path
        if rule.prefix:
            path = (path != '/' and rule.prefix + path) or rule.prefix
        self.path = path
        self.schemes = tuple(rule.schemes)
        self.hostname = rule.hostname
        self.regex = re.compile(self.build_regex(self.path))
        self.pipeline_flow_open = rule.pipeline_flow_open
        self.pipeline_flow_close = rule.pipeline_flow_close
        self.build_matcher()
        self.build_argparser()
        self.build_dispatcher(rule)

    @staticmethod
    def build_regex(path):
        path = REGEX_INT.sub(r'(?P<\g<1>>\\d+)', path)
        path = REGEX_STR.sub(r'(?P<\g<1>>[^/]+)', path)
        path = REGEX_ANY.sub(r'(?P<\g<1>>.*)', path)
        path = REGEX_ALPHA.sub(r'(?P<\g<1>>[^/\\W\\d_]+)', path)
        path = REGEX_DATE.sub(r'(?P<\g<1>>\\d{4}-\\d{2}-\\d{2})', path)
        path = REGEX_FLOAT.sub(r'(?P<\g<1>>\\d+\.\\d+)', path)
        return f'^({path})$'

    def match_simple(self, path):
        return path == self.path, {}

    def match_regex(self, path):
        match = self.regex.match(path)
        if match:
            return True, self.parse_reqargs(match)
        return False, {}

    def build_matcher(self):
        if (
            self._re_condl.findall(self.path) or
            self._re_param.findall(self.path)
        ):
            matcher, is_static = self.match_regex, False
        else:
            matcher, is_static = self.match_simple, True
        self.match = matcher
        self.is_static = is_static

    def build_argparser(self):
        parsers = {
            'int': self._parse_int_reqarg,
            'float': self._parse_float_reqarg,
            'date': self._parse_date_reqarg
        }
        opt_parsers = {
            'int': self._parse_int_reqarg_opt,
            'float': self._parse_float_reqarg_opt,
            'date': self._parse_date_reqarg_opt
        }
        pipeline = []
        for key in parsers.keys():
            optionals = []
            for element in re.compile(
                r'\(([^<]+)?<{}\:(\w+)>\)\?'.format(key)
            ).findall(self.path):
                optionals.append(element[1])
            elements = set(
                re.compile(r'<{}\:(\w+)>'.format(key)).findall(self.path))
            args = elements - set(optionals)
            if args:
                parser = self._wrap_reqargs_parser(parsers[key], args)
                pipeline.append(parser)
            if optionals:
                parser = self._wrap_reqargs_parser(
                    opt_parsers[key], optionals)
                pipeline.append(parser)
        if pipeline:
            self.parse_reqargs = self._wrap_reqargs_pipeline(pipeline)
        else:
            self.parse_reqargs = self._parse_reqargs

    @staticmethod
    def _parse_reqargs(match):
        return match.groupdict()

    @staticmethod
    def _parse_int_reqarg(args, route_args):
        for arg in args:
            route_args[arg] = int(route_args[arg])

    @staticmethod
    def _parse_int_reqarg_opt(args, route_args):
        for arg in args:
            if route_args[arg] is None:
                continue
            route_args[arg] = int(route_args[arg])

    @staticmethod
    def _parse_float_reqarg(args, route_args):
        for arg in args:
            route_args[arg] = float(route_args[arg])

    @staticmethod
    def _parse_float_reqarg_opt(args, route_args):
        for arg in args:
            if route_args[arg] is None:
                continue
            route_args[arg] = float(route_args[arg])

    @staticmethod
    def _parse_date_reqarg(args, route_args):
        try:
            for arg in args:
                route_args[arg] = pendulum.DateTime.strptime(
                    route_args[arg], "%Y-%m-%d")
        except Exception:
            raise HTTP(404)

    @staticmethod
    def _parse_date_reqarg_opt(args, route_args):
        try:
            for arg in args:
                if route_args[arg] is None:
                    continue
                route_args[arg] = pendulum.DateTime.strptime(
                    route_args[arg], "%Y-%m-%d")
        except Exception:
            raise HTTP(404)

    @staticmethod
    def _wrap_reqargs_parser(parser, args):
        @wraps(parser)
        def wrapped(route_args):
            return parser(args, route_args)
        return wrapped

    @staticmethod
    def _wrap_reqargs_pipeline(parsers):
        def wrapped(match):
            route_args = match.groupdict()
            for parser in parsers:
                parser(route_args)
            return route_args
        return wrapped

    def build_dispatcher(self, rule):
        raise NotImplementedError


class HTTPRoute(Route):
    __slots__ = ['methods']

    def __init__(self, rule, path, idx):
        super().__init__(rule, path, idx)
        self.methods = tuple(rule.methods)

    def build_dispatcher(self, rule):
        dispatchers = {
            'base': RequestDispatcher,
            'open': RequestOpenDispatcher,
            'close': RequestCloseDispatcher,
            'flow': RequestFlowDispatcher
        } if not rule.cache_rule else {
            'base': CacheDispatcher,
            'open': CacheOpenDispatcher,
            'close': CacheCloseDispatcher,
            'flow': CacheFlowDispatcher
        }
        if self.pipeline_flow_open and self.pipeline_flow_close:
            dispatcher = dispatchers['flow']
        elif self.pipeline_flow_open and not self.pipeline_flow_close:
            dispatcher = dispatchers['open']
        elif not self.pipeline_flow_open and self.pipeline_flow_close:
            dispatcher = dispatchers['close']
        else:
            dispatcher = dispatchers['base']
        self.dispatcher = dispatcher(self, rule)


class WebsocketRoute(Route):
    __slots__ = ['pipeline_flow_receive', 'pipeline_flow_send']

    def __init__(self, rule, path, idx):
        super().__init__(rule, path, idx)
        self.pipeline_flow_receive = rule.pipeline_flow_receive
        self.pipeline_flow_send = rule.pipeline_flow_send

    def build_dispatcher(self, rule):
        dispatchers = {
            'base': WSDispatcher,
            'open': WSOpenDispatcher,
            'close': WSCloseDispatcher,
            'flow': WSFlowDispatcher
        }
        if self.pipeline_flow_open and self.pipeline_flow_close:
            dispatcher = dispatchers['flow']
        elif self.pipeline_flow_open and not self.pipeline_flow_close:
            dispatcher = dispatchers['open']
        elif not self.pipeline_flow_open and self.pipeline_flow_close:
            dispatcher = dispatchers['close']
        else:
            dispatcher = dispatchers['base']
        self.dispatcher = dispatcher(self)
