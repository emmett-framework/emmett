# -*- coding: utf-8 -*-
"""
    emmett.routing.response
    -----------------------

    Provides response builders for http routes.

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

from __future__ import annotations

from typing import Any, AnyStr, Dict, Tuple, Type, Union

from renoir.errors import TemplateMissingError

from ..ctx import current
from ..helpers import load_component
from ..html import asis
from ..http import HTTPResponse, HTTP, HTTPBytes
from .rules import RoutingRule
from .urls import url

_html_content_type = 'text/html; charset=utf-8'


class ResponseBuilder:
    http_cls: Type[HTTPResponse] = HTTP

    def __init__(self, route: RoutingRule):
        self.route = route

    def __call__(self, output: Any) -> Tuple[Type[HTTPResponse], AnyStr]:
        return self.http_cls, output


class ResponseProcessor(ResponseBuilder):
    def process(self, output: Any):
        raise NotImplementedError

    def __call__(self, output: Any) -> Tuple[Type[HTTPResponse], AnyStr]:
        return self.http_cls, self.process(output)


class BytesResponseBuilder(ResponseBuilder):
    http_cls: Type[HTTPResponse] = HTTPBytes


class TemplateResponseBuilder(ResponseProcessor):
    def process(self, output: Union[Dict[str, Any], None]) -> str:
        current.response.headers._data['content-type'] = _html_content_type
        base_ctx = {
            'current': current,
            'url': url,
            'asis': asis,
            'load_component': load_component
        }
        output = base_ctx if output is None else {**base_ctx, **output}
        try:
            return self.route.app.templater.render(
                self.route.template, output
            )
        except TemplateMissingError as exc:
            raise HTTP(404, body="{}\n".format(exc.message))


class AutoResponseBuilder(ResponseProcessor):
    def process(self, output: Any) -> str:
        is_template = False
        if isinstance(output, dict):
            is_template = True
            output = {
                **{
                    'current': current,
                    'url': url,
                    'asis': asis,
                    'load_component': load_component
                },
                **output
            }
        elif output is None:
            output = {
                'current': current,
                'url': url,
                'asis': asis,
                'load_component': load_component
            }
        if is_template:
            current.response.headers._data['content-type'] = _html_content_type
            try:
                return self.route.app.templater.render(
                    self.route.template, output
                )
            except TemplateMissingError as exc:
                raise HTTP(404, body="{}\n".format(exc.message))
        elif isinstance(output, str):
            return output
        return str(output)
