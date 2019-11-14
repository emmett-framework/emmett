# -*- coding: utf-8 -*-
"""
    weppy.routing.response
    ----------------------

    Provides response builders for http routes.

    :copyright: (c) 2014-2019 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

from ..ctx import current
from ..http import HTTP, HTTPBytes
from ..templating.helpers import TemplateMissingError
from .urls import url


class ResponseBuilder:
    http_cls = HTTP

    def __init__(self, route):
        self.route = route

    def __call__(self, output):
        return self.http_cls, output


class ResponseProcessor(ResponseBuilder):
    def process(self, output):
        return output

    def __call__(self, output):
        return self.http_cls, self.process(output)


class BytesResponseBuilder(ResponseBuilder):
    http_cls = HTTPBytes


class TemplateResponseBuilder(ResponseProcessor):
    def process(self, output):
        if output is None:
            output = {'current': current, 'url': url}
        else:
            output['current'] = output.get('current', current)
            output['url'] = output.get('url', url)
        try:
            return self.route.app.templater.render(
                self.route.template_path, self.route.template, output)
        except TemplateMissingError as exc:
            raise HTTP(404, body="{}\n".format(exc.message))


class AutoResponseBuilder(ResponseProcessor):
    def process(self, output):
        is_template = False
        if isinstance(output, dict):
            is_template = True
            output['current'] = output.get('current', current)
            output['url'] = output.get('url', url)
        elif output is None:
            is_template = True
            output = {'current': current, 'url': url}
        if is_template:
            try:
                return self.route.app.templater.render(
                    self.route.template_path, self.route.template, output)
            except TemplateMissingError as exc:
                raise HTTP(404, body="{}\n".format(exc.message))
        elif isinstance(output, str) or hasattr(output, '__iter__'):
            return output
        return str(output)
