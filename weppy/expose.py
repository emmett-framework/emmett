# -*- coding: utf-8 -*-
"""
    weppy.expose
    ------------

    Provide routing for application, as well as internal url creation.
    The expose module is responsible of dispatching the app dynamic requests.

    :copyright: (c) 2014-2018 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

import asyncio
import os
import pendulum
import re

from collections import OrderedDict
from functools import wraps
from urllib.parse import quote as uquote

from .cache import RouteCacheRule
from .ctx import current
from .http import HTTP, HTTPBytes, HTTPResponse
from .pipeline import Pipeline, Pipe
from .templating.helpers import TemplateMissingError

__all__ = ['Expose', 'url']


class ResponseBuilder(object):
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
            return self.route.application.templater.render(
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
                return self.route.application.templater.render(
                    self.route.template_path, self.route.template, output)
            except TemplateMissingError as exc:
                raise HTTP(404, body="{}\n".format(exc.message))
        elif isinstance(output, str) or hasattr(output, '__iter__'):
            return output
        return str(output)


class MetaExpose(type):
    def __new__(cls, name, bases, attrs):
        nc = type.__new__(cls, name, bases, attrs)
        nc._get_routes_in_for_host = nc._get_routes_in_for_host_simple
        nc.match_lang = nc._match_no_lang
        return nc


def _build_routing_dict():
    rv = {}
    for scheme in ['http', 'https']:
        rv[scheme] = {}
        for method in [
            'GET', 'HEAD', 'POST', 'PUT', 'DELETE', 'OPTIONS', 'PATCH'
        ]:
            rv[scheme][method] = {'static': {}, 'match': OrderedDict()}
    return rv


class Expose(metaclass=MetaExpose):
    _routing_started_ = False
    _routing_stack = []
    _routes_str = OrderedDict()
    application = None
    routes_in = {'__any__': _build_routing_dict()}
    routes_out = {}
    _pipeline = []
    _injectors = []
    _prefix_main = ''
    _prefix_main_len = 0
    _outputs = {
        'auto': AutoResponseBuilder,
        'bytes': BytesResponseBuilder,
        'str': ResponseBuilder,
        'template': TemplateResponseBuilder
    }
    REGEX_INT = re.compile(r'<int\:(\w+)>')
    REGEX_STR = re.compile(r'<str\:(\w+)>')
    REGEX_ANY = re.compile(r'<any\:(\w+)>')
    REGEX_ALPHA = re.compile(r'<alpha\:(\w+)>')
    REGEX_DATE = re.compile(r'<date\:(\w+)>')
    REGEX_FLOAT = re.compile(r'<float\:(\w+)>')

    @classmethod
    def _bind_app_(cls, application, url_prefix=None):
        cls.application = application
        main_prefix = url_prefix or ''
        if main_prefix:
            if main_prefix.endswith('/'):
                main_prefix = main_prefix[:-1]
            if not main_prefix.startswith('/'):
                main_prefix = '/' + main_prefix
            if main_prefix == '/':
                main_prefix = ''
        cls._prefix_main = main_prefix
        cls._prefix_main_len = len(cls._prefix_main)

    def __init__(
        self, paths=None, name=None, template=None, pipeline=None,
        injectors=None, schemes=None, hostname=None, methods=None, prefix=None,
        template_folder=None, template_path=None, cache=None, output='auto'
    ):
        if callable(paths):
            raise SyntaxError('Use @route(), not @route.')
        if not self.__class__._routing_started_:
            self.__class__._routing_started_ = True
            self.application.send_signal('before_routes')
        if self.application.language_force_on_url:
            self.__class__.match_lang = self.__class__._match_with_lang
        self.schemes = schemes or ('http', 'https')
        if not isinstance(self.schemes, (list, tuple)):
            self.schemes = (self.schemes, )
        self.methods = methods or ('get', 'post', 'head')
        if not isinstance(self.methods, (list, tuple)):
            self.methods = (self.methods, )
        self.hostname = hostname
        self.paths = paths
        if self.paths is None:
            self.paths = []
        if not isinstance(self.paths, (list, tuple)):
            self.paths = [self.paths]
        self.name = name
        if output not in self._outputs:
            raise SyntaxError(
                'Invalid output specified. Allowed values are: {}'.format(
                    ', '.join(self._outputs.keys())))
        self.output_type = output
        self.template = template
        self.template_folder = template_folder
        self.template_path = template_path
        self.prefix = prefix
        self.pipeline = (
            self._pipeline + (pipeline or []) +
            self._injectors + (injectors or []))
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
        self._routing_stack.append(self)

    @property
    def folder(self):
        return self.application.root_path

    def build_name(self):
        short = self.filename[1 + len(self.folder):].rsplit('.', 1)[0]
        if not short:
            short = self.filename.rsplit('.', 1)[0]
        if short == "__init__":
            short = self.folder.rsplit('/', 1)[-1]
        # allow only one level of naming if name is builded
        if len(short.split(os.sep)) > 1:
            short = short.split(os.sep)[-1]
        return '.'.join(short.split(os.sep) + [self.f_name])

    @classmethod
    def build_regex(cls, path):
        path = cls.REGEX_INT.sub(r'(?P<\g<1>>\\d+)', path)
        path = cls.REGEX_STR.sub(r'(?P<\g<1>>[^/]+)', path)
        path = cls.REGEX_ANY.sub(r'(?P<\g<1>>.*)', path)
        path = cls.REGEX_ALPHA.sub(r'(?P<\g<1>>[^/\\W\\d_]+)', path)
        path = cls.REGEX_DATE.sub(r'(?P<\g<1>>\\d{4}-\\d{2}-\\d{2})', path)
        path = cls.REGEX_FLOAT.sub(r'(?P<\g<1>>\\d+\.\\d+)', path)
        expr = '^(%s)$' % path
        return expr

    @staticmethod
    def remove_trailslash(path):
        if path[-1] == '/' and path[1:]:
            return path[:-1]
        return path

    @classmethod
    def build_route_components(cls, path):
        rule = re.compile(r'(\()?([^<\w]+)?<(\w+)\:(\w+)>(\)\?)?')
        components = []
        params = []
        for match in rule.findall(path):
            params.append(match[1] + "{}")
        statics = re.compile(rule).sub("{}", path).split("{}")
        if not params:
            components = statics
        else:
            components.append(statics[0])
            for idx, el in enumerate(params):
                components.append(params[idx] + statics[idx + 1])
        return components

    @classmethod
    def add_route(cls, route):
        host = route.hostname or '__any__'
        if host not in cls.routes_in:
            cls.routes_in[host] = _build_routing_dict()
            cls._get_routes_in_for_host = cls._get_routes_in_for_host_all
        for scheme in route.schemes:
            for method in route.methods:
                routing_dict = cls.routes_in[host][scheme][method.upper()]
                if route.is_static:
                    routing_dict['static'][route.path] = route
                else:
                    routing_dict['match'][route.name] = route
        cls.routes_out[route.name] = {
            'host': route.hostname,
            'path': cls.build_route_components(route.path)
        }

    def __call__(self, f):
        self.application.send_signal('before_route', route=self, f=f)
        self.f_name = f.__name__
        self.filename = os.path.realpath(f.__code__.co_filename)
        self.hostname = self.hostname or \
            self.application.config.hostname_default
        if not self.paths:
            self.paths.append("/" + f.__name__)
        if not self.name:
            self.name = self.build_name()
        # is it good?
        if self.name.endswith("."):
            self.name = self.name + self.f_name
        #
        if self.prefix:
            if not self.prefix.startswith('/'):
                self.prefix = '/' + self.prefix
        if not self.template:
            self.template = self.f_name + \
                self.application.template_default_extension
        if self.template_folder:
            self.template = os.path.join(self.template_folder, self.template)
        self.template_path = self.template_path or \
            self.application.template_path
        pipeline_obj = Pipeline(self.pipeline)
        wrapped_f = pipeline_obj(f)
        self.pipeline_flow_open = pipeline_obj._flow_open()
        self.pipeline_flow_close = pipeline_obj._flow_close()
        self.f = wrapped_f
        output_type = pipeline_obj._output_type() or self.output_type
        self.response_builders = {
            method.upper(): self._outputs[output_type](self)
            for method in self.methods
        }
        if 'head' in self.response_builders:
            self.response_builders['head'].http_cls = HTTPResponse
        for idx, path in enumerate(self.paths):
            routeobj = Route(self, path, idx)
            self.add_route(routeobj)
            self._routes_str[routeobj.name] = "%s %s://%s%s%s -> %s" % (
                "|".join(self.methods).upper(),
                "|".join(self.schemes),
                self.hostname or "<any>",
                self._prefix_main,
                routeobj.path,
                self.name
            )
        self.application.send_signal('after_route', route=self)
        self._routing_stack.pop()
        return f

    @classmethod
    def _match_lang(cls, path):
        default = cls.application.language_default
        if len(path) <= 1:
            return path, default
        clean_path = path.lstrip('/')
        lang = clean_path.split('/', 1)[0]
        if lang in cls.application.languages and lang != default:
            new_path = '/'.join([arg for arg in clean_path.split('/')[1:]])
            if path.startswith('/'):
                new_path = '/' + new_path
            return new_path, lang
        return path, default

    @classmethod
    def _get_routes_in_for_host_all(cls, hostname):
        return (
            cls.routes_in.get(hostname, cls.routes_in['__any__']),
            cls.routes_in['__any__'])

    @classmethod
    def _get_routes_in_for_host_simple(cls, hostname):
        return (cls.routes_in['__any__'],)

    @classmethod
    def _match_with_lang(cls, request, path):
        path, lang = cls._match_lang(path)
        current.language = request.language = lang
        return path

    @classmethod
    def _match_no_lang(cls, request, path):
        request.language = None
        return path

    @classmethod
    def match(cls, request):
        path = cls.remove_trailslash(request.path)
        path = cls.match_lang(request, path)
        for routing_dict in cls._get_routes_in_for_host(request.host):
            sub_dict = routing_dict[request.scheme][request.method]
            route = sub_dict['static'].get(path)
            if route:
                return route, {}
            for route in sub_dict['match'].values():
                match, args = route.match(path)
                if match:
                    return route, args
        return None, {}

    @classmethod
    async def dispatch(cls):
        #: get the right exposed function
        request, response = current.request, current.response
        route, reqargs = cls.match(request)
        if not route:
            raise HTTP(404, body="Resource not found\n")
        request.name = route.name
        http_cls, output = await route.dispatch(request, reqargs)
        return http_cls(
            response.status, output, response.headers, response.cookies)

    @classmethod
    def static_versioning(cls):
        return (cls.application.config.static_version_urls and
                cls.application.config.static_version) or ''

    @classmethod
    def exposing(cls):
        return cls._routing_stack[-1]


class Route(object):
    def __init__(self, exposer, path, idx):
        self.exposer = exposer
        self.path = path
        self.name = self.exposer.name if idx == 0 else \
            "{}.{}".format(self.exposer.name, idx)
        self.schemes = self.exposer.schemes
        self.methods = self.exposer.methods
        if not self.path.startswith('/'):
            self.path = '/' + self.path
        if self.prefix:
            self.path = \
                (self.path != '/' and self.prefix + self.path) or self.prefix
        self.regex = re.compile(self.exposer.build_regex(self.path))
        self.build_matcher()
        self.build_argparser()
        self._pipeline_flow_open = self.exposer.pipeline_flow_open
        self._pipeline_flow_close = self.exposer.pipeline_flow_close
        self.build_dispatcher()

    @property
    def hostname(self):
        return self.exposer.hostname

    @property
    def prefix(self):
        return self.exposer.prefix

    @property
    def pipeline(self):
        return self.exposer.pipeline

    @pipeline.setter
    def pipeline(self, pipeline):
        self.exposer.pipeline = pipeline

    @property
    def f(self):
        return self.exposer.f

    @f.setter
    def f(self, f):
        self.exposer.f = f

    def match_simple(self, path):
        return path == self.path, {}

    def match_regex(self, path):
        match = self.regex.match(path)
        if match:
            return True, self.parse_reqargs(match)
        return False, {}

    def build_matcher(self):
        if (
            re.compile(r'\(.*\)\?').findall(self.path) or
            re.compile(r'<(\w+)\:(\w+)>').findall(self.path)
        ):
            matcher, is_static = self.match_regex, False
        else:
            matcher, is_static = self.match_simple, True
        self.match = matcher
        self.is_static = is_static

    def build_argparser(self):
        parsers = {
            'int': Route._parse_int_reqarg,
            'float': Route._parse_float_reqarg,
            'date': Route._parse_date_reqarg
        }
        opt_parsers = {
            'int': Route._parse_int_reqarg_opt,
            'float': Route._parse_float_reqarg_opt,
            'date': Route._parse_date_reqarg_opt
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

    def build_dispatcher(self):
        dispatchers = {
            'base': Dispatcher, 'open': BeforeDispatcher,
            'close': AfterDispatcher, 'flow': CompleteDispatcher
        } if not self.exposer.cache_rule else {
            'base': CacheDispatcher, 'open': BeforeCacheDispatcher,
            'close': AfterCacheDispatcher, 'flow': CompleteCacheDispatcher
        }
        if self._pipeline_flow_open and self._pipeline_flow_close:
            dispatcher = dispatchers['flow']
        elif self._pipeline_flow_open and not self._pipeline_flow_close:
            dispatcher = dispatchers['open']
        elif not self._pipeline_flow_open and self._pipeline_flow_close:
            dispatcher = dispatchers['close']
        else:
            dispatcher = dispatchers['base']
        self.dispatcher = dispatcher(self)

    def dispatch(self, request, reqargs):
        return self.dispatcher.dispatch(request, reqargs)


class Dispatcher(object):
    __slots__ = ('f', 'flow_open', 'flow_close', 'response_builders')

    def __init__(self, route):
        self.f = route.f
        self.flow_open = route._pipeline_flow_open
        self.flow_close = route._pipeline_flow_close
        self.response_builders = route.exposer.response_builders

    async def _parallel_flow(self, flow):
        tasks = [asyncio.create_task(method()) for method in flow]
        await asyncio.gather(*tasks, return_exceptions=True)
        for task in tasks:
            if task.exception():
                raise task.exception()

    def before_dispatch(self):
        return self._parallel_flow(self.flow_open)

    def after_dispatch(self):
        return self._parallel_flow(self.flow_close)

    def build_response(self, request, output):
        return self.response_builders[request.method](output)

    async def get_response(self, request, reqargs):
        return self.build_response(request, await self.f(**reqargs))

    def dispatch(self, request, reqargs):
        return self.get_response(request, reqargs)


class BeforeDispatcher(Dispatcher):
    __slots__ = ()

    async def dispatch(self, request, reqargs):
        await self.before_dispatch()
        return await self.get_response(request, reqargs)


class AfterDispatcher(Dispatcher):
    __slots__ = ()

    async def dispatch(self, request, reqargs):
        try:
            rv = await self.get_response(request, reqargs)
        except Exception:
            await self.after_dispatch()
            raise
        await self.after_dispatch()
        return rv


class CompleteDispatcher(Dispatcher):
    __slots__ = ()

    async def dispatch(self, request, reqargs):
        await self.before_dispatch()
        try:
            rv = await self.get_response(request, reqargs)
        except Exception:
            await self.after_dispatch()
            raise
        await self.after_dispatch()
        return rv


class DispatcherCacheMixin(object):
    __slots__ = ()
    _allowed_methods = {'GET', 'HEAD'}

    def __init__(self, route):
        super().__init__(route)
        self.exposer = route.exposer
        self.rule = route.exposer.cache_rule

    async def get_response(self, request, reqargs):
        if request.method not in self._allowed_methods:
            return await super().get_response(request, reqargs)
        response = current.response
        key = self.rule._build_ctx_key(
            self.exposer, **self.rule._build_ctx(
                reqargs, self.exposer, current))
        data = self.rule.cache.get(key)
        if data is not None:
            response.headers.update(data['headers'])
            return data['http_cls'], data['content']
        http_cls, output = await super().get_response(request, reqargs)
        if response.status == 200:
            self.rule.cache.set(
                key, {
                    'http_cls': http_cls,
                    'content': output,
                    'headers': response.headers},
                self.rule.duration)
        return http_cls, output


class CacheDispatcher(DispatcherCacheMixin, Dispatcher):
    __slots__ = ('exposer', 'rule')


class BeforeCacheDispatcher(DispatcherCacheMixin, BeforeDispatcher):
    __slots__ = ('exposer', 'rule')


class AfterCacheDispatcher(DispatcherCacheMixin, AfterDispatcher):
    __slots__ = ('exposer', 'rule')


class CompleteCacheDispatcher(DispatcherCacheMixin, CompleteDispatcher):
    __slots__ = ('exposer', 'rule')


class ResponsePipe(Pipe):
    def __init__(self, route):
        self.route = route

    async def pipe(self, next_pipe, **kwargs):
        return self.route.response_builders[current.request.method](
            await next_pipe(**kwargs))


class CachedResponsePipe(Pipe):
    def __init__(self, route, rule):
        self.route = route
        self.rule = rule
        self._allowed_methods = {'GET', 'HEAD'}

    async def pipe(self, next_pipe, **kwargs):
        if current.request.method not in self._allowed_methods:
            return await next_pipe(**kwargs)
        response = current.response
        key = self.rule._build_ctx_key(
            self.route, **self.rule._build_ctx(kwargs, self.route, current))
        data = self.rule.cache.get(key)
        if data is not None:
            response.headers.update(data['headers'])
            return data['http_cls'], data['content']
        http_cls, output = await next_pipe(**kwargs)
        if response.status == 200:
            self.rule.cache.set(
                key, {
                    'http_cls': http_cls,
                    'content': output,
                    'headers': response.headers},
                self.rule.duration)
        return http_cls, output


class RouteUrl(object):
    def __init__(self, components=[]):
        if not components:
            self.components = ['/{}']
            self._args = ['']
        else:
            self.components = ['{}'] + components[1:]
            self._args = [components[0]]

    @property
    def path(self):
        return self._args[0]

    def arg(self, value):
        if not self.components:
            self.components.append('/{}')
        return self.components.pop(0).format(value)

    def add_static_versioning(self, args):
        if self.path.startswith('/static') and Expose.static_versioning():
            self.components.insert(1, "/_{}")
            args.insert(1, str(Expose.static_versioning()))

    def add_prefix(self, args):
        if Expose._prefix_main:
            self.components.insert(0, '{}')
            args.insert(0, Expose._prefix_main)

    def add_language(self, args, language):
        if language:
            self.components.insert(0, '/{}')
            args.insert(0, language)

    def path_prefix(self, scheme, host):
        if scheme and host:
            return '{}://{}'.format(scheme, host)
        return ''

    def args(self, args):
        rv = ''
        for arg in args:
            rv += self.arg(arg)
        return rv

    def params(self, params):
        if params:
            return '?' + '&'.join(
                '%s=%s' % (uquote(str(k)), uquote(str(v)))
                for k, v in params.items()
            )
        return ''

    def anchor(self, anchor):
        rv = ''
        if anchor:
            if not isinstance(anchor, (list, tuple)):
                anchor = [anchor]
            for element in anchor:
                rv += '#{}'.format(element)
        return rv

    def url(self, scheme, host, language, args, params, anchor):
        args = self._args + args
        self.add_static_versioning(args)
        self.add_language(args, language)
        self.add_prefix(args)
        return "{}{}{}{}".format(
            self.path_prefix(scheme, host), self.args(args),
            self.params(params), self.anchor(anchor))


def url(
    path, args=[], params={}, anchor=None, sign=None, scheme=None, host=None,
    language=None
):
    if not isinstance(args, (list, tuple)):
        args = [args]
    # allow user to use url('static', 'file')
    if path == 'static':
        path = '/static'
    # routes urls with 'dot' notation
    if '/' not in path:
        # urls like 'function' refers to same module
        if '.' not in path:
            namespace = Expose.application.config.url_default_namespace or \
                Expose.application.name
            path = namespace + "." + path
        # urls like '.function' refers to main app module
        elif path.startswith('.'):
            if not hasattr(current, 'request'):
                raise RuntimeError(
                    'cannot build url("%s",...) without current request' % path
                )
            module = current.request.name.rsplit('.', 1)[0]
            path = module + path
        # find correct route
        try:
            url_components = Expose.routes_out[path]['path']
            url_host = Expose.routes_out[path]['host']
            builder = RouteUrl(url_components)
            # try to use the correct hostname
            if url_host is not None:
                try:
                    if current.request.host != url_host:
                        scheme = current.request.scheme
                        host = url_host
                except Exception:
                    pass
        except KeyError:
            raise RuntimeError('invalid url("%s",...)' % path)
    # handle classic urls
    else:
        builder = RouteUrl([path])
    # add language
    lang = None
    if Expose.application.language_force_on_url:
        if language:
            #: use the given language if is enabled in application
            if language in Expose.application.languages:
                lang = language
        else:
            #: try to use the request language if context exists
            if hasattr(current, 'request'):
                lang = current.request.language
        if lang == Expose.application.language_default:
            lang = None
    # # add extension (useless??)
    # if extension:
    #     url = url + '.' + extension
    # scheme=True means to use current scheme
    if scheme is True:
        if not hasattr(current, 'request'):
            raise RuntimeError(
                'cannot build url("%s",...) without current request' % path
            )
        scheme = current.request.scheme
    # add scheme and host
    if scheme:
        if host is None:
            if not hasattr(current, 'request'):
                raise RuntimeError(
                    'cannot build url("%s",...) without current request' % path
                )
            host = current.request.host
    # add signature
    if sign:
        if '_signature' in params:
            del params['_signature']
        params['_signature'] = sign(
            path, args, params, anchor, scheme, host, language)
    return builder.url(scheme, host, lang, args, params, anchor)
