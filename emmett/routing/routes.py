# -*- coding: utf-8 -*-
"""
emmett.routing.routes
---------------------

Provides routes objects.

:copyright: 2014 Giovanni Barillari
:license: BSD-3-Clause
"""

import re
from functools import wraps

import pendulum
from emmett_core.http.response import HTTPResponse
from emmett_core.routing.routes import HTTPRoute as _HTTPRoute


class HTTPRoute(_HTTPRoute):
    __slots__ = []

    def __init__(self, rule, path, idx):
        super().__init__(rule, path, idx)
        self.build_argparser()

    def build_argparser(self):
        parsers = {"date": self._parse_date_reqarg}
        opt_parsers = {"date": self._parse_date_reqarg_opt}
        pipeline = []
        for key in parsers.keys():
            optionals = []
            for element in re.compile(r"\(([^<]+)?<{}\:(\w+)>\)\?".format(key)).findall(self.path):
                optionals.append(element[1])
            elements = set(re.compile(r"<{}\:(\w+)>".format(key)).findall(self.path))
            args = elements - set(optionals)
            if args:
                parser = self._wrap_reqargs_parser(parsers[key], args)
                pipeline.append(parser)
            if optionals:
                parser = self._wrap_reqargs_parser(opt_parsers[key], optionals)
                pipeline.append(parser)
        if pipeline:
            for key, dispatcher in self.dispatchers.items():
                self.dispatchers[key] = DispacherWrapper(dispatcher, pipeline)

    @staticmethod
    def _parse_date_reqarg(args, route_args):
        try:
            for arg in args:
                dt = route_args[arg]
                route_args[arg] = pendulum.datetime(dt.year, dt.month, dt.day)
        except Exception:
            raise HTTPResponse(404)

    @staticmethod
    def _parse_date_reqarg_opt(args, route_args):
        try:
            for arg in args:
                if route_args[arg] is None:
                    continue
                dt = route_args[arg]
                route_args[arg] = pendulum.datetime(dt.year, dt.month, dt.day)
        except Exception:
            raise HTTPResponse(404)

    @staticmethod
    def _wrap_reqargs_parser(parser, args):
        @wraps(parser)
        def wrapped(route_args):
            return parser(args, route_args)

        return wrapped


class DispacherWrapper:
    __slots__ = ["dispatcher", "parsers"]

    def __init__(self, dispatcher, parsers):
        self.dispatcher = dispatcher
        self.parsers = parsers

    def dispatch(self, reqargs, response):
        for parser in self.parsers:
            parser(reqargs)
        return self.dispatcher.dispatch(reqargs, response)
