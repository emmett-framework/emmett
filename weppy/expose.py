# -*- coding: utf-8 -*-
"""
    weppy.expose
    ------------

    Provide routing for application, as well as internal url creation.
    The expose module is responsible of dispatching the app dynamic requests.

    :copyright: (c) 2014-2017 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

import os
import pendulum
import re
from collections import OrderedDict
from functools import wraps
from ._compat import PY2, with_metaclass, itervalues, iteritems, text_type
from ._internal import warn_of_deprecation
from .pipeline import Pipeline, Pipe
from .templating.helpers import TemplateMissingError
from .globals import current
from .http import HTTP

if PY2:
    from urllib import quote as uquote
else:
    from urllib.parse import quote as uquote

__all__ = ['Expose', 'url']


class MetaExpose(type):
    def __new__(cls, name, bases, attrs):
        nc = type.__new__(cls, name, bases, attrs)
        nc._get_routes_in_for_host = nc._get_routes_in_for_host_simple
        return nc


class Expose(with_metaclass(MetaExpose)):
    _routing_started_ = False
    _routing_stack = []
    _routes_str = OrderedDict()
    application = None
    routes_in = {'__any__': OrderedDict()}
    routes_out = {}
    _pipeline = []
    _injectors = []
    REGEX_INT = re.compile('<int\:(\w+)>')
    REGEX_STR = re.compile('<str\:(\w+)>')
    REGEX_ANY = re.compile('<any\:(\w+)>')
    REGEX_ALPHA = re.compile('<alpha\:(\w+)>')
    REGEX_DATE = re.compile('<date\:(\w+)>')
    REGEX_FLOAT = re.compile('<float\:(\w+)>')
    REGEX_DECORATION = re.compile(
        '(([?*+])|(\([^()]*\))|(\[[^\[\]]*\])|(\<[^<>]*\>))')

    def __init__(
        self, paths=None, name=None, template=None, pipeline=None,
        injectors=None, schemes=None, hostname=None, methods=None, prefix=None,
        template_folder=None, template_path=None, **kwargs
    ):
        if callable(paths):
            raise SyntaxError('Use @route(), not @route.')
        if not Expose._routing_started_:
            Expose._routing_started_ = True
            self.application.send_signal('before_routes')
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
        self.template = template
        self.template_folder = template_folder
        self.template_path = template_path
        self.prefix = prefix
        if 'handlers' in kwargs:
            warn_of_deprecation('handlers', 'pipeline', 'route', 3)
            pipeline = kwargs['handlers']
        if 'helpers' in kwargs:
            warn_of_deprecation('helpers', 'injectors', 'route', 3)
            injectors = kwargs['helpers']
        self.pipeline = [ResponsePipe(self)] + self._pipeline + \
            (pipeline or []) + self._injectors + (injectors or [])
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
    def build_regex(cls, schemes, hostname, methods, path):
        path = cls.REGEX_INT.sub('(?P<\g<1>>\d+)', path)
        path = cls.REGEX_STR.sub('(?P<\g<1>>[^/]+)', path)
        path = cls.REGEX_ANY.sub('(?P<\g<1>>.*)', path)
        path = cls.REGEX_ALPHA.sub('(?P<\g<1>>[^/\W\d_]+)', path)
        path = cls.REGEX_DATE.sub('(?P<\g<1>>\d{4}-\d{2}-\d{2})', path)
        path = cls.REGEX_FLOAT.sub('(?P<\g<1>>\d+\.\d+)', path)
        re_schemes = ('|'.join(schemes)).lower()
        re_methods = ('|'.join(methods)).upper()
        re_hostname = re.escape(hostname) if hostname else '[^/]*'
        expr = '^(%s) (%s)\://(%s)(%s)$' % \
            (re_methods, re_schemes, re_hostname, path)
        return expr

    @staticmethod
    def remove_trailslash(path):
        if path[-1] == '/' and path[1:]:
            return path[:-1]
        return path

    @classmethod
    def build_route_components(cls, path):
        rule = re.compile("(\()?([^<\w]+)?<(\w+)\:(\w+)>(\)\?)?")
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
        host = route[1].hostname or '__any__'
        if host not in cls.routes_in:
            cls.routes_in[host] = OrderedDict()
            cls._get_routes_in_for_host = cls._get_routes_in_for_host_all
        cls.routes_in[host][route[1].name] = route
        cls.routes_out[route[1].name] = {
            'host': route[1].hostname,
            'path': cls.build_route_components(route[1].path)}

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
        wrapped_f = Pipeline(self.pipeline)(f)
        self.f = wrapped_f
        for idx, path in enumerate(self.paths):
            routeobj = Route(self, path, idx)
            route = (re.compile(routeobj.regex), routeobj)
            self.add_route(route)
            self._routes_str[routeobj.name] = "%s %s://%s%s -> %s" % (
                "|".join(self.methods).upper(),
                "|".join(self.schemes),
                self.hostname or "<any>",
                routeobj.path,
                self.name
            )
        self.application.send_signal('after_route', route=self)
        self._routing_stack.pop()
        return f

    @classmethod
    def match_lang(cls, path):
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
    def match(cls, request):
        path = cls.remove_trailslash(request.path_info)
        if cls.application.language_force_on_url:
            path, lang = cls.match_lang(path)
            current.language = request.language = lang
        else:
            request.language = None
        expression = '%s %s://%s%s' % (
            request.method, request.scheme, request.hostname, path)
        for routes in cls._get_routes_in_for_host(request.hostname):
            for regex, obj in itervalues(routes):
                match = regex.match(expression)
                if match:
                    return obj, obj.parse_reqargs(match)
        return None, {}

    @staticmethod
    def _before_dispatch(route):
        #: call pipeline `before_flow` method
        for pipe in route.pipeline:
            pipe.open()

    @staticmethod
    def _after_dispatch(route):
        #: call pipeline `after_flow` method
        for pipe in reversed(route.pipeline):
            pipe.close()

    @classmethod
    def dispatch(cls):
        #: get the right exposed function
        request = current.request
        route, reqargs = cls.match(request)
        if not route:
            raise HTTP(404, body="Resource not found\n")
        request.name = route.name
        cls._before_dispatch(route)
        try:
            route.f(**reqargs)
        except Exception:
            cls._after_dispatch(route)
            raise
        cls._after_dispatch(route)

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
        self.regex = self.exposer.build_regex(
            self.schemes, self.hostname, self.methods, self.path)
        self.build_argparser()

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
                "\(([^<]+)?<{}\:(\w+)>\)\?".format(key)
            ).findall(self.path):
                optionals.append(element[1])
            elements = set(
                re.compile("<{}\:(\w+)>".format(key)).findall(self.path))
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
                route_args[arg] = pendulum.strptime(
                    route_args[arg], "%Y-%m-%d")
        except Exception:
            raise HTTP(404)

    @staticmethod
    def _parse_date_reqarg_opt(args, route_args):
        try:
            for arg in args:
                if route_args[arg] is None:
                    continue
                route_args[arg] = pendulum.strptime(
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


class ResponsePipe(Pipe):
    def __init__(self, route):
        self.route = route

    def pipe(self, next_pipe, **kwargs):
        response = current.response
        output = next_pipe(**kwargs)
        if output is None:
            output = {'current': current, 'url': url}
        if isinstance(output, dict):
            output['current'] = output.get('current', current)
            output['url'] = output.get('url', url)
            try:
                output = Expose.application.templater.render(
                    self.route.template_path, self.route.template, output)
            except TemplateMissingError as exc:
                raise HTTP(404, body="{}\n".format(exc.message))
            response.output = output
        elif isinstance(output, text_type) or hasattr(output, '__iter__'):
            response.output = output
        else:
            response.output = str(output)


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
        if self.path[0:7] == '/static' and Expose.static_versioning():
            self.components.insert(1, "/_{}")
            args.insert(1, str(Expose.static_versioning()))

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
                for k, v in iteritems(params)
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
                    if current.request.hostname != url_host:
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
            host = current.request.hostname
    # add signature
    if sign:
        if '_signature' in params:
            del params['_signature']
        params['_signature'] = sign(
            path, args, params, anchor, scheme, host, language)
    return builder.url(scheme, host, lang, args, params, anchor)
