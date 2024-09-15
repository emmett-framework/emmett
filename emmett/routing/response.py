# -*- coding: utf-8 -*-
"""
    emmett.routing.response
    -----------------------

    Provides response builders for http routes.

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

from __future__ import annotations

from typing import Any, Dict, Union

from emmett_core.http.response import HTTPStringResponse
from emmett_core.routing.response import ResponseProcessor
from renoir.errors import TemplateMissingError

from ..ctx import current
from ..helpers import load_component
from ..html import asis
from .urls import url

_html_content_type = 'text/html; charset=utf-8'


class TemplateResponseBuilder(ResponseProcessor):
    def process(
        self,
        output: Union[Dict[str, Any], None],
        response
    ) -> str:
        response.headers._data['content-type'] = _html_content_type
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
            raise HTTPStringResponse(
                404,
                body="{}\n".format(exc.message),
                cookies=response.cookies
            )


class AutoResponseBuilder(ResponseProcessor):
    def process(self, output: Any, response) -> str:
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
            response.headers._data['content-type'] = _html_content_type
            try:
                return self.route.app.templater.render(
                    self.route.template, output
                )
            except TemplateMissingError as exc:
                raise HTTPStringResponse(
                    404,
                    body="{}\n".format(exc.message),
                    cookies=response.cookies
                )
        elif isinstance(output, str):
            return output
        return str(output)
