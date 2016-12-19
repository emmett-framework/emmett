# -*- coding: utf-8 -*-
"""
    weppy.expose
    ------------

    Provide routing for application, as well as internal url creation.
    The expose module is responsible of dispatching the app dynamic requests.

    :copyright: (c) 2014-2016 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

import re
import os
from collections import OrderedDict
from datetime import datetime
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
    _routing_stack = []
    _routes_str = OrderedDict()
    application = None
    routes_in = {'__any__': OrderedDict()}
    routes_out = {}
    _pipeline = []
    _injectors = []
    processors = []
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
        re_methods = ('|'.join(methods)).lower()
        re_hostname = re.escape(hostname) if hostname else '[^/]*'
        expr = '^(%s) (%s)\://(%s)(%s)$' % \
            (re_methods, re_schemes, re_hostname, path)
        return expr

    @staticmethod
    def remove_trailslash(path):
        if path.endswith("/") and len(path) > 1:
            return path[:-1]
        return path

    @staticmethod
    def override_midargs(path):
        args = path.split("//")
        if len(args) > 1:
            path = "/{{:arg:}}/".join(args)
        return path

    @classmethod
    def remove_decoration(cls, path):
        """
        converts somehing like "/junk/test_args/<str:a>(/<int:b>)?"
        into something like    "/junk/test_args" for reverse routing
        """
        while True:
            new_path = cls.REGEX_DECORATION.sub('', path)
            new_path = cls.remove_trailslash(new_path)
            new_path = cls.override_midargs(new_path)
            if new_path == path:
                return path
            path = new_path

    @classmethod
    def add_route(cls, route):
        host = route[1].hostname or '__any__'
        if host not in cls.routes_in:
            cls.routes_in[host] = OrderedDict()
            cls._get_routes_in_for_host = cls._get_routes_in_for_host_all
        cls.routes_in[host][route[1].name] = route
        cls.routes_out[route[1].name] = {
            'host': route[1].hostname,
            'path': cls.remove_decoration(route[1].path)}

    def __call__(self, f):
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
                "|".join(s.upper() for s in self.methods),
                "|".join(s for s in self.schemes),
                self.hostname or "<any>",
                routeobj.path,
                self.name
            )
        for proc_handler in self.processors:
            proc_handler(self)
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
            request.language = lang
            current._language = request.language
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
            raise HTTP(404, body="Invalid action\n")
        request.name = route.name
        cls._before_dispatch(route)
        try:
            route.f(**reqargs)
        except:
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
            "{}_{}".format(self.exposer.name, idx)
        self.schemes = self.exposer.schemes
        self.methods = self.exposer.methods
        self.pipeline = self.exposer.pipeline
        self.f = self.exposer.f
        if not self.path.startswith('/'):
            self.path = '/' + self.path
        if self.exposer.prefix:
            self.path = (
                (self.path != '/' and self.prefix + self.path) or
                self.exposer.prefix)
        self.regex = self.exposer.build_regex(
            self.schemes, self.hostname, self.methods, self.path)
        self.build_argparser()

    @property
    def hostname(self):
        return self.exposer.hostname

    @property
    def prefix(self):
        return self.exposer.prefix

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
                route_args[arg] = datetime.strptime(
                    route_args[arg], "%Y-%m-%d")
        except Exception:
            raise HTTP(404)

    @staticmethod
    def _parse_date_reqarg_opt(args, route_args):
        try:
            for arg in args:
                if route_args[arg] is None:
                    continue
                route_args[arg] = datetime.strptime(
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
            except TemplateMissingError:
                raise HTTP(404, body="Invalid view\n")
            response.output = output
        elif isinstance(output, text_type) or hasattr(output, '__iter__'):
            response.output = output
        else:
            response.output = str(output)


def url(
    path, args=[], params={}, extension=None, sign=None, scheme=None,
    host=None, language=None
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
            url = Expose.routes_out[path]['path']
            url_host = Expose.routes_out[path]['host']
            # try to rebuild url if midargs found
            midargs = url.split("{{:arg:}}")
            if len(midargs) > 1:
                u = ""
                if len(args) >= len(midargs) - 1:
                    for i in range(0, len(midargs) - 1):
                        u += midargs[i] + uquote(str(args[i]))
                    u += midargs[-1]
                    url = u
                    args = args[len(midargs) - 1:]
                else:
                    raise RuntimeError(
                        'invalid url("%s",...): needs args for params' % path
                    )
            # try to use the correct hostname
            if url_host is not None:
                try:
                    if current.request.hostname != url_host:
                        #url = current.request.scheme+"://"+url_host+url
                        scheme = current.request.scheme
                        host = url_host
                except:
                    pass
        except KeyError:
            raise RuntimeError('invalid url("%s",...)' % path)
    # handle classic urls
    else:
        url = path
    # add static versioning
    if url[0:7] == '/static':
        if Expose.static_versioning():
            url = url[0:7] + "/_" + str(Expose.static_versioning()) + url[7:]
    # language
    if Expose.application.language_force_on_url:
        if url.startswith("/"):
            lang = None
            if language:
                #: use the given language if is enabled in application
                if language in Expose.application.languages:
                    lang = language
            else:
                #: try to use the request language if context exists
                if hasattr(current, 'request'):
                    lang = current.request.language
            if lang and lang != Expose.application.language_default:
                url = '/' + lang + url
    # add extension (useless??)
    if extension:
        url = url + '.' + extension
    # add args
    if args:
        if not isinstance(args, (list, tuple)):
            args = (args,)
        url = url + '/' + '/'.join(uquote(str(a)) for a in args)
    # add signature
    if sign:
        params['_signature'] = sign(url)
    # add params
    if params:
        url = url + '?' + '&'.join(
            '%s=%s' % (
                uquote(str(k)), uquote(str(v))) for k, v in iteritems(params)
        )
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
        url = '%s://%s%s' % (scheme, host, url)
    return url
