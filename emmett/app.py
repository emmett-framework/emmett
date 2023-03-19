# -*- coding: utf-8 -*-
"""
    emmett.app
    ----------

    Provides the central application object.

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

from __future__ import annotations

import os
import sys

from logging import Logger
from typing import Any, Awaitable, Callable, Dict, List, Optional, Set, Type, Union

import click

from yaml import SafeLoader as ymlLoader, load as ymlload

from ._internal import get_root_path, create_missing_app_folders, warn_of_deprecation
from .asgi import handlers as asgi_handlers
from .cache import RouteCacheRule
from .ctx import current
from .datastructures import sdict, ConfigData
from .extensions import Extension, ExtensionType, Signals
from .helpers import load_component
from .html import asis
from .language.helpers import Tstr
from .language.translator import Translator
from .pipeline import Pipe, Injector
from .routing.router import HTTPRouter, WebsocketRouter, RoutingCtx, RoutingCtxGroup
from .routing.urls import url
from .rsgi import handlers as rsgi_handlers
from .templating.templater import Templater
from .testing import EmmettTestClient
from .typing import ErrorHandlerType
from .utils import dict_to_sdict, cachedprop, read_file


class Config(ConfigData):
    __slots__ = ()

    def __init__(self, app: App):
        self._app = app
        super().__init__(
            modules_class=AppModule,
            hostname_default=None,
            static_version=None,
            static_version_urls=False,
            url_default_namespace=None,
            request_max_content_length=None,
            request_body_timeout=None,
            response_timeout=None
        )
        self._handle_static = True
        self._templates_auto_reload = app.debug or False
        self._templates_encoding = 'utf8'
        self._templates_escape = 'common'
        self._templates_indent = False

    def __setattr__(self, key, value):
        obj = getattr(self.__class__, key, None)
        if isinstance(obj, property):
            return obj.fset(self, value)
        return super().__setattr__(key, value)

    @property
    def handle_static(self) -> bool:
        return self._handle_static

    @handle_static.setter
    def handle_static(self, value: bool):
        self._handle_static = value
        self._app._configure_asgi_handlers()

    @property
    def templates_auto_reload(self) -> bool:
        return self._templates_auto_reload

    @templates_auto_reload.setter
    def templates_auto_reload(self, value: bool):
        self._templates_auto_reload = value
        self._app.templater._set_reload(value)

    @property
    def templates_encoding(self) -> str:
        return self._templates_encoding

    @templates_encoding.setter
    def templates_encoding(self, value: str):
        self._templates_encoding = value
        self._app.templater._set_encoding(value)

    @property
    def templates_escape(self) -> str:
        return self._templates_escape

    @templates_escape.setter
    def templates_escape(self, value: str):
        self._templates_escape = value
        self._app.templater._set_escape(value)

    @property
    def templates_adjust_indent(self) -> bool:
        return self._templates_adjust_indent

    @templates_adjust_indent.setter
    def templates_adjust_indent(self, value: bool):
        self._templates_adjust_indent = value
        self._app.templater._set_indent(value)


class App:
    __slots__ = [
        '__dict__',
        '_asgi_handlers',
        '_extensions_env',
        '_extensions_listeners',
        '_language_default',
        '_language_force_on_url',
        '_languages_set',
        '_languages',
        '_logger',
        '_modules',
        '_pipeline',
        '_router_http',
        '_router_ws',
        'cli',
        'config_path',
        'config',
        'error_handlers',
        'ext',
        'import_name',
        'logger_name',
        'root_path',
        'static_path',
        'template_default_extension',
        'template_path',
        'templater',
        'translator'
    ]

    debug = None
    test_client_class = None

    def __init__(
        self,
        import_name: str,
        root_path: Optional[str] = None,
        url_prefix: Optional[str] = None,
        template_folder: str = 'templates',
        config_folder: str = 'config'
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
        self.cli = click.Group(self.import_name)
        #: init the configuration
        self.config = Config(self)
        #: try to create needed folders
        create_missing_app_folders(self)
        #: init languages
        self._languages: List[str] = []
        self._languages_set: Set[str] = set()
        self._language_default: Optional[str] = None
        self._language_force_on_url = False
        self.translator = Translator(
            os.path.join(self.root_path, 'languages'),
            default_language=self.language_default or 'en',
            watch_changes=self.debug,
            str_class=Tstr
        )
        #: init routing
        self._pipeline: List[Pipe] = []
        self._router_http = HTTPRouter(self, url_prefix=url_prefix)
        self._router_ws = WebsocketRouter(self, url_prefix=url_prefix)
        self._asgi_handlers = {
            'http': asgi_handlers.HTTPHandler(self),
            'lifespan': asgi_handlers.LifeSpanHandler(self),
            'websocket': asgi_handlers.WSHandler(self)
        }
        self._rsgi_handlers = {
            'http': rsgi_handlers.HTTPHandler(self),
            'ws': rsgi_handlers.WSHandler(self)
        }
        self.error_handlers: Dict[int, Callable[[], Awaitable[str]]] = {}
        self.template_default_extension = '.html'
        #: init logger
        self._logger = None
        self.logger_name = self.import_name
        #: init extensions
        self.ext: sdict[str, Extension] = sdict()
        self._extensions_env: sdict[str, Any] = sdict()
        self._extensions_listeners: Dict[str, List[Callable[..., Any]]] = {
            element.value: [] for element in Signals
        }
        #: init templater
        self.templater: Templater = Templater(
            path=self.template_path,
            encoding=self.config.templates_encoding,
            escape=self.config.templates_escape,
            adjust_indent=self.config.templates_adjust_indent,
            reload=self.config.templates_auto_reload
        )
        #: finalise
        self._modules: Dict[str, AppModule] = {}
        current.app = self

    def _configure_asgi_handlers(self):
        self._asgi_handlers['http']._configure_methods()
        self._rsgi_handlers['http']._configure_methods()

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
    def languages(self) -> List[str]:
        return self._languages

    @languages.setter
    def languages(self, value: List[str]):
        self._languages = value
        self._languages_set = set(self._languages)

    @property
    def language_default(self) -> Optional[str]:
        return self._language_default

    @language_default.setter
    def language_default(self, value: str):
        self._language_default = value
        self.translator._update_config(self._language_default or 'en')

    @property
    def language_force_on_url(self) -> bool:
        return self._language_force_on_url

    @language_force_on_url.setter
    def language_force_on_url(self, value: bool):
        self._language_force_on_url = value
        self._router_http._set_language_handling()
        self._router_ws._set_language_handling()
        self._configure_asgi_handlers()

    @property
    def pipeline(self) -> List[Pipe]:
        return self._pipeline

    @pipeline.setter
    def pipeline(self, pipes: List[Pipe]):
        self._pipeline = pipes
        self._router_http.pipeline = self._pipeline
        self._router_ws.pipeline = self._pipeline

    @property
    def injectors(self) -> List[Injector]:
        return self._router_http.injectors

    @injectors.setter
    def injectors(self, injectors: List[Injector]):
        self._router_http.injectors = injectors

    def route(
        self,
        paths: Optional[Union[str, List[str]]] = None,
        name: Optional[str] = None,
        template: Optional[str] = None,
        pipeline: Optional[List[Pipe]] = None,
        injectors: Optional[List[Injector]] = None,
        schemes: Optional[Union[str, List[str]]] = None,
        hostname: Optional[str] = None,
        methods: Optional[Union[str, List[str]]] = None,
        prefix: Optional[str] = None,
        template_folder: Optional[str] = None,
        template_path: Optional[str] = None,
        cache: Optional[RouteCacheRule] = None,
        output: str = 'auto'
    ) -> RoutingCtx:
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
        self,
        paths: Optional[Union[str, List[str]]] = None,
        name: Optional[str] = None,
        pipeline: Optional[List[Pipe]] = None,
        schemes: Optional[Union[str, List[str]]] = None,
        hostname: Optional[str] = None,
        prefix: Optional[str] = None
    ) -> RoutingCtx:
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

    def on_error(self, code: int) -> Callable[[ErrorHandlerType], ErrorHandlerType]:
        def decorator(f: ErrorHandlerType) -> ErrorHandlerType:
            self.error_handlers[code] = f
            return f
        return decorator

    @property
    def command(self):
        return self.cli.command

    @property
    def command_group(self):
        return self.cli.group

    @property
    def log(self) -> Logger:
        if self._logger and self._logger.name == self.logger_name:
            return self._logger
        from .logger import _logger_lock, create_logger
        with _logger_lock:
            if self._logger and self._logger.name == self.logger_name:
                return self._logger
            self._logger = rv = create_logger(self)
            return rv

    def render_template(self, filename: str) -> str:
        ctx = {
            'current': current, 'url': url, 'asis': asis,
            'load_component': load_component
        }
        return self.templater.render(filename, ctx)

    def config_from_yaml(self, filename: str, namespace: Optional[str] = None):
        #: import configuration from yaml files
        rc = read_file(os.path.join(self.config_path, filename))
        rc = ymlload(rc, Loader=ymlLoader)
        c = self.config if namespace is None else self.config[namespace]
        for key, val in rc.items():
            c[key] = dict_to_sdict(val)

    #: Register modules
    def _register_module(self, mod: AppModule):
        self._modules[mod.name] = mod

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
    def use_extension(self, ext_cls: Type[ExtensionType]) -> ExtensionType:
        if not issubclass(ext_cls, Extension):
            raise RuntimeError(
                f'{ext_cls.__name__} is an invalid Emmett extension'
            )
        ext_env, ext_config = self.__init_extension(ext_cls)
        ext = self.ext[ext_cls.__name__] = ext_cls(self, ext_env, ext_config)
        self.__register_extension_listeners(ext)
        ext.on_load()
        return ext

    #: Add a template extension to application
    def use_template_extension(self, ext_cls, **config):
        return self.templater.use_extension(ext_cls, **config)

    def send_signal(self, signal: Union[str, Signals], *args, **kwargs):
        if not isinstance(signal, Signals):
            warn_of_deprecation(
                "App.send_signal str argument",
                "extensions.Signals as argument",
                stack=3
            )
            try:
                signal = Signals[signal]
            except KeyError:
                raise SyntaxError(f"{signal} is not a valid signal")
        for listener in self._extensions_listeners[signal]:
            listener(*args, **kwargs)

    def make_shell_context(self, context: Dict[str, Any] = {}) -> Dict[str, Any]:
        context['app'] = self
        return context

    def test_client(self, use_cookies: bool = True, **kwargs) -> EmmettTestClient:
        tclass = self.test_client_class or EmmettTestClient
        return tclass(self, use_cookies=use_cookies, **kwargs)

    def __call__(self, scope, receive, send):
        return self._asgi_handlers[scope['type']](scope, receive, send)

    def __rsgi__(self, scope, protocol):
        return self._rsgi_handlers[scope.proto](scope, protocol)

    def __rsgi_init__(self, loop):
        self.send_signal(Signals.after_loop, loop=loop)

    def module(
        self,
        import_name: str,
        name: str,
        template_folder: Optional[str] = None,
        template_path: Optional[str] = None,
        static_folder: Optional[str] = None,
        static_path: Optional[str] = None,
        url_prefix: Optional[str] = None,
        hostname: Optional[str] = None,
        cache: Optional[RouteCacheRule] = None,
        root_path: Optional[str] = None,
        pipeline: Optional[List[Pipe]] = None,
        injectors: Optional[List[Injector]] = None,
        module_class: Optional[Type[AppModule]] = None,
        **kwargs: Any
    ) -> AppModule:
        module_class = module_class or self.config.modules_class
        return module_class.from_app(
            self,
            import_name,
            name,
            template_folder=template_folder,
            template_path=template_path,
            static_folder=static_folder,
            static_path=static_path,
            url_prefix=url_prefix,
            hostname=hostname,
            cache=cache,
            root_path=root_path,
            pipeline=pipeline or [],
            injectors=injectors or [],
            opts=kwargs
        )

    def module_group(self, *modules: AppModule) -> AppModuleGroup:
        return AppModuleGroup(*modules)


class AppModule:
    @classmethod
    def from_app(
        cls,
        app: App,
        import_name: str,
        name: str,
        template_folder: Optional[str],
        template_path: Optional[str],
        static_folder: Optional[str],
        static_path: Optional[str],
        url_prefix: Optional[str],
        hostname: Optional[str],
        cache: Optional[RouteCacheRule],
        root_path: Optional[str],
        pipeline: List[Pipe],
        injectors: List[Injector],
        opts: Dict[str, Any] = {}
    ):
        return cls(
            app,
            name,
            import_name,
            template_folder=template_folder,
            template_path=template_path,
            static_folder=static_folder,
            static_path=static_path,
            url_prefix=url_prefix,
            hostname=hostname,
            cache=cache,
            root_path=root_path,
            pipeline=pipeline,
            injectors=injectors,
            **opts
        )

    @classmethod
    def from_module(
        cls,
        appmod: AppModule,
        import_name: str,
        name: str,
        template_folder: Optional[str],
        template_path: Optional[str],
        static_folder: Optional[str],
        static_path: Optional[str],
        url_prefix: Optional[str],
        hostname: Optional[str],
        cache: Optional[RouteCacheRule],
        root_path: Optional[str],
        opts: Dict[str, Any] = {}
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
            appmod.app,
            name,
            import_name,
            template_folder=template_folder,
            template_path=template_path,
            static_folder=static_folder,
            static_path=static_path,
            url_prefix=module_url_prefix,
            hostname=hostname,
            cache=cache,
            root_path=root_path,
            pipeline=appmod.pipeline,
            injectors=appmod.injectors,
            **opts
        )

    @classmethod
    def from_module_group(
        cls,
        appmodgroup: AppModuleGroup,
        import_name: str,
        name: str,
        template_folder: Optional[str],
        template_path: Optional[str],
        static_folder: Optional[str],
        static_path: Optional[str],
        url_prefix: Optional[str],
        hostname: Optional[str],
        cache: Optional[RouteCacheRule],
        root_path: Optional[str],
        opts: Dict[str, Any] = {}
    ) -> AppModulesGrouped:
        mods = []
        for module in appmodgroup.modules:
            mod = cls.from_module(
                module,
                import_name,
                name,
                template_folder=template_folder,
                template_path=template_path,
                static_folder=static_folder,
                static_path=static_path,
                url_prefix=url_prefix,
                hostname=hostname,
                cache=cache,
                root_path=root_path,
                opts=opts
            )
            mods.append(mod)
        return AppModulesGrouped(*mods)

    def module(
        self,
        import_name: str,
        name: str,
        template_folder: Optional[str] = None,
        template_path: Optional[str] = None,
        static_folder: Optional[str] = None,
        static_path: Optional[str] = None,
        url_prefix: Optional[str] = None,
        hostname: Optional[str] = None,
        cache: Optional[RouteCacheRule] = None,
        root_path: Optional[str] = None,
        module_class: Optional[Type[AppModule]] = None,
        **kwargs: Any
    ) -> AppModule:
        module_class = module_class or self.__class__
        return module_class.from_module(
            self,
            import_name,
            name,
            template_folder=template_folder,
            template_path=template_path,
            static_folder=static_folder,
            static_path=static_path,
            url_prefix=url_prefix,
            hostname=hostname,
            cache=cache,
            root_path=root_path,
            opts=kwargs
        )

    def __init__(
        self,
        app: App,
        name: str,
        import_name: str,
        template_folder: Optional[str] = None,
        template_path: Optional[str] = None,
        static_folder: Optional[str] = None,
        static_path: Optional[str] = None,
        url_prefix: Optional[str] = None,
        hostname: Optional[str] = None,
        cache: Optional[RouteCacheRule] = None,
        root_path: Optional[str] = None,
        pipeline: Optional[List[Pipe]] = None,
        injectors: Optional[List[Injector]] = None,
        **kwargs: Any
    ):
        self.app = app
        self.name = name
        self.import_name = import_name
        if root_path is None:
            root_path = get_root_path(self.import_name)
        self.root_path = root_path
        #: - `template_folder` is referred to application `template_path`
        #  - `template_path` is referred to module root_directory unless absolute
        self.template_folder = template_folder
        if template_path and not template_path.startswith("/"):
            template_path = os.path.join(self.root_path, template_path)
        self.template_path = template_path
        #: - `static_folder` is referred to application `static_path`
        #  - `static_path` is referred to module root_directory unless absolute
        if static_path and not static_path.startswith("/"):
            static_path = os.path.join(self.root_path, static_path)
        self._static_path = (
            os.path.join(self.app.static_path, static_folder) if static_folder else
            (static_path or self.app.static_path)
        )
        self.url_prefix = url_prefix
        self.hostname = hostname
        self.cache = cache
        self._super_pipeline = pipeline or []
        self._super_injectors = injectors or []
        self.pipeline = []
        self.injectors = []
        self.app._register_module(self)

    @property
    def pipeline(self) -> List[Pipe]:
        return self._pipeline

    @pipeline.setter
    def pipeline(self, pipeline: List[Pipe]):
        self._pipeline = self._super_pipeline + pipeline

    @property
    def injectors(self) -> List[Injector]:
        return self._injectors

    @injectors.setter
    def injectors(self, injectors: List[Injector]):
        self._injectors = self._super_injectors + injectors

    def route(
        self,
        paths: Optional[Union[str, List[str]]] = None,
        name: Optional[str] = None,
        template: Optional[str] = None,
        **kwargs
    ) -> RoutingCtx:
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

    def websocket(
        self,
        paths: Optional[Union[str, List[str]]] = None,
        name: Optional[str] = None,
        **kwargs
    ) -> RoutingCtx:
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


class AppModuleGroup:
    def __init__(self, *modules: AppModule):
        self.modules = modules

    def module(
        self,
        import_name: str,
        name: str,
        template_folder: Optional[str] = None,
        template_path: Optional[str] = None,
        static_folder: Optional[str] = None,
        static_path: Optional[str] = None,
        url_prefix: Optional[str] = None,
        hostname: Optional[str] = None,
        cache: Optional[RouteCacheRule] = None,
        root_path: Optional[str] = None,
        module_class: Optional[Type[AppModule]] = None,
        **kwargs: Any
    ) -> AppModulesGrouped:
        module_class = module_class or AppModule
        return module_class.from_module_group(
            self,
            import_name,
            name,
            template_folder=template_folder,
            template_path=template_path,
            static_folder=static_folder,
            static_path=static_path,
            url_prefix=url_prefix,
            hostname=hostname,
            cache=cache,
            root_path=root_path,
            opts=kwargs
        )

    def route(
        self,
        paths: Optional[Union[str, List[str]]] = None,
        name: Optional[str] = None,
        template: Optional[str] = None,
        **kwargs
    ) -> RoutingCtxGroup:
        return RoutingCtxGroup([
            mod.route(paths=paths, name=name, template=template, **kwargs)
            for mod in self.modules
        ])

    def websocket(
        self,
        paths: Optional[Union[str, List[str]]] = None,
        name: Optional[str] = None,
        **kwargs
    ):
        return RoutingCtxGroup([
            mod.websocket(paths=paths, name=name, **kwargs)
            for mod in self.modules
        ])


class AppModulesGrouped(AppModuleGroup):
    @property
    def pipeline(self) -> List[List[Pipe]]:
        return [module.pipeline for module in self.modules]

    @pipeline.setter
    def pipeline(self, pipeline: List[Pipe]):
        for module in self.modules:
            module.pipeline = pipeline

    @property
    def injectors(self) -> List[List[Injector]]:
        return [module.injectors for module in self.modules]

    @injectors.setter
    def injectors(self, injectors: List[Injector]):
        for module in self.modules:
            module.injectors = injectors
