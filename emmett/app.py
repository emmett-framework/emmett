# -*- coding: utf-8 -*-
"""
    emmett.app
    ----------

    Provides the central application object.

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

import click
import os
import sys

from yaml import SafeLoader as ymlLoader, load as ymlload

from ._internal import get_root_path, create_missing_app_folders
from .asgi.handlers import HTTPHandler, LifeSpanHandler, WSHandler
from .asgi.server import run as asgi_run
from .ctx import current
from .datastructures import sdict, ConfigData
from .extensions import Extension
from .helpers import load_component
from .html import asis
from .language.helpers import Tstr
from .language.translator import Translator
from .routing.router import HTTPRouter, WebsocketRouter
from .routing.urls import url
from .templating.templater import Templater
from .utils import dict_to_sdict, cachedprop, read_file


class Config(ConfigData):
    __slots__ = ()

    def __init__(self, app):
        self._app = app
        super().__init__(
            modules_class=AppModule,
            hostname_default=None,
            static_version=None,
            static_version_urls=False,
            url_default_namespace=None,
            request_max_content_length=None,
            request_body_timeout=None
        )
        self._handle_static = True
        self._templates_auto_reload = app.debug or False
        self._templates_encoding = 'utf8'
        self._templates_escape = 'common'
        self._templates_prettify = False

    def __setattr__(self, key, value):
        obj = getattr(self.__class__, key, None)
        if isinstance(obj, property):
            return obj.fset(self, value)
        return super().__setattr__(key, value)

    @property
    def handle_static(self):
        return self._handle_static

    @handle_static.setter
    def handle_static(self, value):
        self._handle_static = value
        self._app._configure_asgi_handlers()

    @property
    def templates_auto_reload(self):
        return self._templates_auto_reload

    @templates_auto_reload.setter
    def templates_auto_reload(self, value):
        self._templates_auto_reload = value
        self._app.templater._set_reload(value)

    @property
    def templates_encoding(self):
        return self._templates_encoding

    @templates_encoding.setter
    def templates_encoding(self, value):
        self._templates_encoding = value
        self._app.templater._set_encoding(value)

    @property
    def templates_escape(self):
        return self._templates_escape

    @templates_escape.setter
    def templates_escape(self, value):
        self._templates_escape = value
        self._app.templater._set_escape(value)

    @property
    def templates_prettify(self):
        return self._templates_prettify

    @templates_prettify.setter
    def templates_prettify(self, value):
        self._templates_prettify = value
        self._app.templater._set_prettify(value)


class App:
    __slots__ = [
        'import_name', 'cli', 'config',
        'root_path', 'static_path', 'template_path', 'config_path',
        'translator', '_languages', '_languages_set',
        '_language_default', '_language_force_on_url',
        '_pipeline', '_router_http', '_router_ws', '_asgi_handlers',
        'error_handlers',
        '_logger', 'logger_name',
        'ext', '_extensions_env', '_extensions_listeners',
        'templater', 'template_default_extension',
        '__dict__'
    ]

    debug = None
    test_client_class = None

    def __init__(
        self, import_name, root_path=None, url_prefix=None,
        template_folder='templates', config_folder='config'
    ):
        self.import_name = import_name
        #: init debug var
        self.debug = os.environ.get('EMMETT_RUN_ENV') == "true"
        #: set paths for the application
        if root_path is None:
            root_path = get_root_path(self.import_name)
        self.root_path = root_path
        self.static_path = os.path.join(self.root_path, "static")
        self.template_path = os.path.join(self.root_path, template_folder)
        self.config_path = os.path.join(self.root_path, config_folder)
        #: the click command line context for this application
        self.cli = click.Group(self)
        #: init the configuration
        self.config = Config(self)
        #: try to create needed folders
        create_missing_app_folders(self)
        #: init languages
        self._languages = []
        self._languages_set = set()
        self._language_default = None
        self._language_force_on_url = False
        self.translator = Translator(
            os.path.join(self.root_path, 'languages'),
            default_language=self.language_default or 'en',
            watch_changes=self.debug,
            str_class=Tstr
        )
        #: init routing
        self._pipeline = []
        self._router_http = HTTPRouter(self, url_prefix=url_prefix)
        self._router_ws = WebsocketRouter(self, url_prefix=url_prefix)
        self._asgi_handlers = {
            'http': HTTPHandler(self),
            'lifespan': LifeSpanHandler(self),
            'websocket': WSHandler(self)
        }
        self.error_handlers = {}
        self.template_default_extension = '.html'
        #: init logger
        self._logger = None
        self.logger_name = self.import_name
        #: init extensions
        self.ext = sdict()
        self._extensions_env = sdict()
        self._extensions_listeners = {key: [] for key in Extension._signals_}
        #: init templater
        self.templater = Templater(
            path=self.template_path,
            encoding=self.config.templates_encoding,
            escape=self.config.templates_escape,
            prettify=self.config.templates_prettify,
            reload=self.config.templates_auto_reload
        )
        #: store app in current
        current.app = self

    def _configure_asgi_handlers(self):
        self._asgi_handlers['http']._configure_methods()

    @cachedprop
    def name(self):
        if self.import_name == '__main__':
            fn = getattr(sys.modules['__main__'], '__file__', None)
            if fn is None:
                rv = '__main__'
            else:
                rv = os.path.splitext(os.path.basename(fn))[0]
        else:
            rv = self.import_name
        return rv

    @property
    def languages(self):
        return self._languages

    @languages.setter
    def languages(self, value):
        self._languages = value
        self._languages_set = set(self._languages)

    @property
    def language_default(self):
        return self._language_default

    @language_default.setter
    def language_default(self, value):
        self._language_default = value
        self.translator._update_config(self._language_default or 'en')

    @property
    def language_force_on_url(self):
        return self._language_force_on_url

    @language_force_on_url.setter
    def language_force_on_url(self, value):
        self._language_force_on_url = value
        self._router_http._set_language_handling()
        self._router_ws._set_language_handling()
        self._configure_asgi_handlers()

    @property
    def pipeline(self):
        return self._pipeline

    @pipeline.setter
    def pipeline(self, pipes):
        self._pipeline = pipes
        self._router_http.pipeline = self._pipeline
        self._router_ws.pipeline = self._pipeline

    @property
    def injectors(self):
        return self.route._injectors

    @injectors.setter
    def injectors(self, injectors):
        self.route._injectors = injectors

    def route(
        self, paths=None, name=None, template=None, pipeline=None,
        injectors=None, schemes=None, hostname=None, methods=None, prefix=None,
        template_folder=None, template_path=None, cache=None, output='auto'
    ):
        if callable(paths):
            raise SyntaxError('Use @route(), not @route.')
        return self._router_http(
            paths=paths,
            name=name,
            template=template,
            pipeline=pipeline,
            injectors=injectors,
            schemes=schemes,
            hostname=hostname,
            methods=methods,
            prefix=prefix,
            template_folder=template_folder,
            template_path=template_path,
            cache=cache,
            output=output
        )

    def websocket(
        self, paths=None, name=None, pipeline=None, schemes=None,
        hostname=None, prefix=None
    ):
        if callable(paths):
            raise SyntaxError('Use @websocket(), not @websocket.')
        return self._router_ws(
            paths=paths,
            name=name,
            pipeline=pipeline,
            schemes=schemes,
            hostname=hostname,
            prefix=prefix
        )

    def on_error(self, code):
        def decorator(f):
            self.error_handlers[code] = f
            return f
        return decorator

    @property
    def command(self):
        return self.cli.command

    @property
    def log(self):
        if self._logger and self._logger.name == self.logger_name:
            return self._logger
        from .logger import _logger_lock, create_logger
        with _logger_lock:
            if self._logger and self._logger.name == self.logger_name:
                return self._logger
            self._logger = rv = create_logger(self)
            return rv

    def render_template(self, filename):
        ctx = {
            'current': current, 'url': url, 'asis': asis,
            'load_component': load_component
        }
        return self.templater.render(filename, ctx)

    def config_from_yaml(self, filename, namespace=None):
        #: import configuration from yaml files
        rc = read_file(os.path.join(self.config_path, filename))
        rc = ymlload(rc, Loader=ymlLoader)
        c = self.config if namespace is None else self.config[namespace]
        for key, val in rc.items():
            c[key] = dict_to_sdict(val)

    #: Creates the extensions' environments and configs
    def __init_extension(self, ext):
        if ext.namespace is None:
            ext.namespace = ext.__name__
        if self._extensions_env[ext.namespace] is None:
            self._extensions_env[ext.namespace] = sdict()
        return self._extensions_env[ext.namespace], self.config[ext.namespace]

    #: Register extension listeners
    def __register_extension_listeners(self, ext):
        for signal, listener in ext._listeners_:
            self._extensions_listeners[signal].append(listener)

    #: Add an extension to application
    def use_extension(self, ext_cls):
        if not issubclass(ext_cls, Extension):
            raise RuntimeError(
                f'{ext_cls.__name__} is an invalid emmett extension')
        ext_env, ext_config = self.__init_extension(ext_cls)
        self.ext[ext_cls.__name__] = ext_cls(self, ext_env, ext_config)
        self.__register_extension_listeners(self.ext[ext_cls.__name__])
        self.ext[ext_cls.__name__].on_load()

    #: Add a template extension to application
    def use_template_extension(self, ext_cls, **config):
        return self.templater.use_extension(ext_cls, **config)

    def send_signal(self, signal, *args, **kwargs):
        for listener in self._extensions_listeners[signal]:
            listener(*args, **kwargs)

    def make_shell_context(self, context={}):
        """Returns the shell context for an interactive shell for this
        application.  This runs all the registered shell context
        processors.
        """
        context['app'] = self
        return context

    def _run(
        self, host, port,
        loop='auto', proto_http='auto', proto_ws='auto',
        log_level=None, access_log=None,
        proxy_headers=False,
        limit_concurrency=None,
        timeout_keep_alive=0
    ):
        asgi_run(
            self, host, port,
            loop=loop, proto_http=proto_http, proto_ws=proto_ws,
            log_level=log_level, access_log=access_log,
            proxy_headers=proxy_headers,
            limit_concurrency=limit_concurrency,
            timeout_keep_alive=timeout_keep_alive
        )

    def run(self, host=None, port=None, reloader=True, debug=True):
        if host is None:
            host = "127.0.0.1"
        if port is None:
            port = 8000
        self.debug = debug
        if os.environ.get('EMMETT_RUN_MAIN') != 'true':
            quit_msg = "(press CTRL+C to quit)"
            self.log.info(
                f"> Emmett application {self.import_name} running on "
                f"http://{host}:{port} {quit_msg}"
            )
        if reloader:
            from ._reloader import run_with_reloader
            run_with_reloader(self, host, port)
        else:
            self._run(host, port)

    def test_client(self, use_cookies=True, **kwargs):
        tclass = self.test_client_class
        if tclass is None:
            from .testing import EmmettTestClient
            tclass = EmmettTestClient
        return tclass(self, use_cookies=use_cookies, **kwargs)

    def __call__(self, scope, receive, send):
        return self._asgi_handlers[scope['type']](scope, receive, send)

    def module(
        self, import_name, name, template_folder=None, template_path=None,
        url_prefix=None, hostname=None, cache=None, root_path=None,
        module_class=None
    ):
        module_class = module_class or self.config.modules_class
        return module_class.from_app(
            self, import_name, name, template_folder, template_path,
            url_prefix, hostname, cache, root_path
        )


class AppModule:
    @classmethod
    def from_app(
        cls, app, import_name, name, template_folder, template_path,
        url_prefix, hostname, cache, root_path
    ):
        return cls(
            app, name, import_name, template_folder, template_path, url_prefix,
            hostname, cache, root_path
        )

    @classmethod
    def from_module(
        cls, appmod, import_name, name, template_folder, template_path,
        url_prefix, hostname, cache, root_path
    ):
        if '.' in name:
            raise RuntimeError(
                "Nested app modules' names should not contains dots"
            )
        name = appmod.name + '.' + name
        if url_prefix and not url_prefix.startswith('/'):
            url_prefix = '/' + url_prefix
        module_url_prefix = (appmod.url_prefix + (url_prefix or '')) \
            if appmod.url_prefix else url_prefix
        hostname = hostname or appmod.hostname
        cache = cache or appmod.cache
        return cls(
            appmod.app, name, import_name, template_folder, template_path,
            module_url_prefix, hostname, cache, root_path,
            pipeline=appmod.pipeline, injectors=appmod.injectors
        )

    def module(
        self, import_name, name, template_folder=None, template_path=None,
        url_prefix=None, hostname=None, cache=None, root_path=None,
        module_class=None
    ):
        module_class = module_class or self.__class__
        return module_class.from_module(
            self, import_name, name, template_folder, template_path,
            url_prefix, hostname, cache, root_path
        )

    def __init__(
        self, app, name, import_name, template_folder=None, template_path=None,
        url_prefix=None, hostname=None, cache=None, root_path=None,
        pipeline=[], injectors=[]
    ):
        self.app = app
        self.name = name
        self.import_name = import_name
        if root_path is None:
            root_path = get_root_path(self.import_name)
        self.root_path = root_path
        #: template_folder is referred to application template_path
        self.template_folder = template_folder
        #: template_path is referred to module root_directory
        if template_path and not template_path.startswith("/"):
            template_path = self.root_path + template_path
        self.template_path = template_path
        self.url_prefix = url_prefix
        self.hostname = hostname
        self.cache = cache
        self._super_pipeline = pipeline
        self._super_injectors = injectors
        self.pipeline = []
        self.injectors = []

    @property
    def pipeline(self):
        return self._pipeline

    @pipeline.setter
    def pipeline(self, pipeline):
        self._pipeline = self._super_pipeline + pipeline

    @property
    def injectors(self):
        return self._injectors

    @injectors.setter
    def injectors(self, injectors):
        self._injectors = self._super_injectors + injectors

    def route(self, paths=None, name=None, template=None, **kwargs):
        if name is not None and "." in name:
            raise RuntimeError(
                "App modules' route names should not contains dots"
            )
        name = self.name + "." + (name or "")
        pipeline = kwargs.get('pipeline', [])
        injectors = kwargs.get('injectors', [])
        if self.pipeline:
            pipeline = self.pipeline + pipeline
        kwargs['pipeline'] = pipeline
        if self.injectors:
            injectors = self.injectors + injectors
        kwargs['injectors'] = injectors
        kwargs['cache'] = kwargs.get('cache', self.cache)
        return self.app.route(
            paths=paths,
            name=name,
            template=template,
            prefix=self.url_prefix,
            template_folder=self.template_folder,
            template_path=self.template_path,
            hostname=self.hostname,
            **kwargs
        )

    def websocket(self, paths=None, name=None, **kwargs):
        if name is not None and "." in name:
            raise RuntimeError(
                "App modules' websocket names should not contains dots"
            )
        name = self.name + "." + (name or "")
        pipeline = kwargs.get('pipeline', [])
        if self.pipeline:
            pipeline = self.pipeline + pipeline
        kwargs['pipeline'] = pipeline
        return self.app.websocket(
            paths=paths,
            name=name,
            prefix=self.url_prefix,
            hostname=self.hostname,
            **kwargs
        )
