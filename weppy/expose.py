# -*- coding: utf-8 -*-
"""
    weppy.expose
    ------------

    Provide routing for application, as well as internal url creation.
    The expose module is responsible of dispatching the app dynamic requests.

    :copyright: (c) 2015 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

import re
import os

from ._compat import PY2, iteritems, text_type, to_native
from .handlers import Handler, _wrapWithHandlers
from .templating import render
from .globals import current
from .tags import TAG
from .http import HTTP

if PY2:
    from urllib import quote as uquote
else:
    from urllib.parse import quote as uquote

__all__ = ['Expose', 'url']


class Expose(object):
    _routing_stack = []
    application = None
    routes_in = {'__any__': []}
    routes_out = {}
    common_handlers = []
    common_helpers = []
    REGEX_INT = re.compile('<int\:(\w+)>')
    REGEX_STR = re.compile('<str\:(\w+)>')
    REGEX_ANY = re.compile('<any\:(\w+)>')
    REGEX_ALPHA = re.compile('<str\:(\w+)>')
    REGEX_DATE = re.compile('<date\:(\w+)>')
    REGEX_DECORATION = re.compile('(([?*+])|(\([^()]*\))|(\[[^\[\]]*\])|(\<[^<>]*\>))')

    def __init__(self, path=None, name=None, template=None, handlers=None,
                 helpers=None, schemes=None, hostname=None, methods=None,
                 prefix=None, template_folder=None, template_path=None):
        if callable(path):
            raise SyntaxError('@expose(), not @expose')
        self.schemes = schemes or ('http', 'https')
        if not isinstance(self.schemes, (list, tuple)):
            self.schemes = (self.schemes,)
        self.methods = methods or ('get', 'post', 'head')
        if not isinstance(self.methods, (list, tuple)):
            self.methods = (self.methods,)
        self.hostname = hostname
        self.path = path
        self.name = name
        self.template = template
        self.template_folder = template_folder
        self.template_path = template_path
        self.prefix = prefix
        self.handlers = self.common_handlers + (handlers or []) + \
            self.common_helpers + (helpers or [])
        # check handlers are indeed valid handlers
        if any(not isinstance(handler, Handler) for handler in self.handlers):
            raise RuntimeError('Invalid Handler')
        Expose._routing_stack.append(self)

    @property
    def folder(self):
        return Expose.application.template_path

    def build_name(self):
        short = self.filename[1+len(self.folder):].rsplit('.', 1)[0]
        if not short:
            short = self.filename.rsplit('.', 1)[0]
        if short == "__init__":
            short = self.folder.rsplit('/', 1)[-1]
        ## allow only one level of naming if name is builded
        if len(short.split(os.sep)) > 1:
            short = short.split(os.sep)[-1]
        return '.'.join(short.split(os.sep) + [self.func_name])

    @staticmethod
    def build_regex(schemes, hostname, methods, path):
        path = Expose.REGEX_INT.sub('(?P<\g<1>>\d+)', path)
        path = Expose.REGEX_STR.sub('(?P<\g<1>>[^/]+)', path)
        path = Expose.REGEX_ANY.sub('(?P<\g<1>>.*)', path)
        path = Expose.REGEX_ALPHA.sub('(?P<\g<1>>\w+)', path)
        path = Expose.REGEX_DATE.sub('(?P<\g<1>>\d{4}-\d{2}-\d{2})', path)
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

    @staticmethod
    def remove_decoration(path):
        """
        converts somehing like "/junk/test_args/<str:a>(/<int:b>)?"
        into something like    "/junk/test_args" for reverse routing
        """
        while True:
            new_path = Expose.REGEX_DECORATION.sub('', path)
            new_path = Expose.remove_trailslash(new_path)
            new_path = Expose.override_midargs(new_path)
            if new_path == path:
                return path
            else:
                path = new_path

    @staticmethod
    def add_route(route):
        host = route[1].hostname or '__any__'
        if host not in Expose.routes_in:
            Expose.routes_in[host] = []
        Expose.routes_in[host].append(route)
        Expose.routes_out[route[1].name] = {
            'host': route[1].hostname,
            'path': Expose.remove_decoration(route[1].path)}

    def __call__(self, func):
        self.func_name = func.__name__
        self.filename = os.path.realpath(func.__code__.co_filename)
        #self.mtime = os.path.getmtime(self.filename)
        self.hostname = self.hostname or \
            Expose.application.config.hostname_default
        if not self.path:
            #self.path = '/' + func.__name__ + '(.\w+)?'
            self.path = '/' + func.__name__
        if not self.name:
            self.name = self.build_name()
        # is it good?
        if self.name.endswith("."):
            self.name = self.name + self.func_name
        #
        if not self.path.startswith('/'):
            self.path = '/'+self.path
        if self.prefix:
            if not self.prefix.startswith('/'):
                self.prefix = '/'+self.prefix
            self.path = (self.path != '/' and self.prefix+self.path) \
                or self.prefix
        if not self.template:
            self.template = self.func_name + '.<ext>'
        #if self.name.startswith('.'):
        #    self.name = '%s%s' % (self.application, self.name)
        if self.template_folder:
            self.template = os.path.join(self.template_folder, self.template)
        self.template_path = self.template_path or self.folder
        wrapped_func = _wrapWithHandlers(self.handlers)(func)
        self.func = wrapped_func
        self.regex = Expose.build_regex(
            self.schemes, self.hostname, self.methods, self.path)
        route = (re.compile(self.regex), self)
        Expose.add_route(route)
        logstr = "%s %s://%s%s" % (
            "|".join(s.upper() for s in self.methods),
            "|".join(s for s in self.schemes),
            self.hostname or "<any>",
            self.path
        )
        self.application.log.info("exposing '%s': %s" % (self.name, logstr))
        Expose._routing_stack.pop()
        return func

    @staticmethod
    def match_lang(path):
        default = Expose.application.language_default
        if len(path) <= 1:
            return path, default
        clean_path = path.lstrip('/')
        lang = clean_path.split('/', 1)[0]
        if lang in Expose.application.languages and lang != default:
            new_path = '/'.join([arg for arg in clean_path.split('/')[1:]])
            if path.startswith('/'):
                new_path = '/'+new_path
            return new_path, lang
        return path, default

    @staticmethod
    def match(request):
        path = Expose.remove_trailslash(request.path_info)
        if Expose.application.language_force_on_url:
            path, lang = Expose.match_lang(path)
            request.language = lang
            current._language = request.language
        else:
            request.language = None
        expression = '%s %s://%s%s' % (
            request.method, request.scheme, request.hostname, path)
        routes_in = Expose.routes_in.get(request.hostname,
                                         Expose.routes_in['__any__'])
        for regex, obj in routes_in:
            match = regex.match(expression)
            if match:
                return obj, match.groupdict()
        return None, {}

    @staticmethod
    def _after_dispatch(route):
        #: call handlers `on_end` method
        for handler in reversed(route.handlers):
            handler.on_end()

    @staticmethod
    def dispatch():
        #: get the right exposed function
        request = current.request
        route, reqargs = Expose.match(request)
        if route:
            request.name = route.name
            try:
                output = route.func(**reqargs)
            except:
                Expose._after_dispatch(route)
                raise
            if output is None:
                output = dict()
        else:
            raise HTTP(404, body="Invalid action\n")
        #: build the right output
        response = current.response
        try:
            if isinstance(output, text_type):
                response.output = [to_native(output)]
            elif isinstance(output, dict):
                if 'current' not in output:
                    output['current'] = current
                if 'url' not in output:
                    output['url'] = url
                templatename = route.template.replace(
                    '.<ext>', Expose.application.template_default_extension)
                output = render(Expose.application, route.template_path,
                                templatename, output)
                response.output = [output]
            elif isinstance(output, TAG):
                response.output = [str(output)]
            elif hasattr(output, '__iter__'):
                response.output = output
            else:
                response.output = [str(output)]
        except:
            Expose._after_dispatch(route)
            raise
        #: end the dispatching
        Expose._after_dispatch(route)

    @staticmethod
    def static_versioning():
        return (Expose.application.config.static_version_urls and
                Expose.application.config.static_version) or ''

    @staticmethod
    def exposing():
        return Expose._routing_stack[-1]


def url(path, args=[], vars={}, extension=None, sign=None, scheme=None,
        host=None):
    """
    usages:
        url('index') # assumes app or default expose file
        url('.index') # use current exposed file
        url('mod.index') # index function in 'mod' module
        url('static', 'file') # for static files
        url('/myurl') # a normal url
    """

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
                if len(args) >= len(midargs)-1:
                    for i in range(0, len(midargs)-1):
                        u += midargs[i]+uquote(str(args[i]))
                    u += midargs[-1]
                    url = u
                    args = args[len(midargs)-1:]
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
            url = url[0:7] + "/_"+str(Expose.static_versioning()) + url[7:]
    # language
    if Expose.application.language_force_on_url:
        if url.startswith("/") and hasattr(current, 'request'):
            if current.request.language != Expose.application.language_default:
                url = '/'+current.request.language+url
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
        vars['_signature'] = sign(url)
    # add vars
    if vars:
        url = url + '?' + '&'.join(
            '%s=%s' % (uquote(k), uquote(v)) for k, v in iteritems(vars)
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
