# -*- coding: utf-8 -*-
"""
    emmett.routing.response
    -----------------------

    Provides response builders for http routes.

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

from __future__ import annotations

from typing import Any, AnyStr, Dict, Tuple, Union

from renoir.errors import TemplateMissingError

from ..ctx import current
from ..helpers import load_component
from ..html import asis
from ..http import HTTPResponse, HTTP, HTTPBytes
from .rules import RoutingRule
from .urls import url


class ResponseBuilder:
    http_cls: HTTPResponse = HTTP

    def __init__(self, route: RoutingRule):
        self.route = route

    def __call__(self, output: Any) -> Tuple[HTTPResponse, AnyStr]:
        return self.http_cls, output


class ResponseProcessor(ResponseBuilder):
    def process(self, output: Any):
        raise NotImplementedError

    def __call__(self, output: Any) -> Tuple[HTTPResponse, AnyStr]:
        return self.http_cls, self.process(output)


class BytesResponseBuilder(ResponseBuilder):
    http_cls: HTTPResponse = HTTPBytes


class TemplateResponseBuilder(ResponseProcessor):
    def process(self, output: Union[Dict[str, Any], None]) -> str:
        if output is None:
            output = {
                'current': current, 'url': url, 'asis': asis,
                'load_component': load_component
            }
        else:
            output['current'] = output.get('current', current)
            output['url'] = output.get('url', url)
            output['asis'] = output.get('asis', asis)
            output['load_component'] = output.get(
                'load_component', load_component)
        try:
            return self.route.app.templater.render(
                self.route.template, output)
        except TemplateMissingError as exc:
            raise HTTP(404, body="{}\n".format(exc.message))


class AutoResponseBuilder(ResponseProcessor):
    def process(self, output: Any) -> str:
        is_template = False
        if isinstance(output, dict):
            is_template = True
            output['current'] = output.get('current', current)
            output['url'] = output.get('url', url)
            output['asis'] = output.get('asis', asis)
            output['load_component'] = output.get(
                'load_component', load_component)
        elif output is None:
            is_template = True
            output = {
                'current': current, 'url': url, 'asis': asis,
                'load_component': load_component
            }
        if is_template:
            try:
                return self.route.app.templater.render(
                    self.route.template, output)
            except TemplateMissingError as exc:
                raise HTTP(404, body="{}\n".format(exc.message))
        elif isinstance(output, str):
            return output
        return str(output)
