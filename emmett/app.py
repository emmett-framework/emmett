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
from typing import Any, Dict, List, Optional, Type, Union

import click
from emmett_core._internal import create_missing_app_folders, get_root_path
from emmett_core.app import App as _App, AppModule as _AppModule, AppModuleGroup as _AppModuleGroup, Config as _Config
from emmett_core.routing.cache import RouteCacheRule
from yaml import SafeLoader as ymlLoader, load as ymlload

from .asgi.handlers import HTTPHandler as ASGIHTTPHandler, WSHandler as ASGIWSHandler
from .ctx import current
from .extensions import Signals
from .helpers import load_component
from .html import asis
from .language.helpers import Tstr
from .language.translator import Translator
from .pipeline import Injector, Pipe
from .routing.router import HTTPRouter, RoutingCtx, RoutingCtxGroup, WebsocketRouter
from .routing.urls import url
from .rsgi.handlers import HTTPHandler as RSGIHTTPHandler, WSHandler as RSGIWSHandler
from .templating.templater import Templater
from .testing import EmmettTestClient
from .utils import dict_to_sdict, read_file


class Config(_Config):
    __slots__ = ()

    def __init__(self, app: App):
        super().__init__(app)
        self._templates_auto_reload = app.debug or False
        self._templates_encoding = "utf8"
        self._templates_escape = "common"
        self._templates_indent = False

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


class AppModule(_AppModule):
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
        opts: Dict[str, Any] = {},
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
            **opts,
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
        opts: Dict[str, Any] = {},
    ):
        if "." in name:
            raise RuntimeError("Nested app modules' names should not contains dots")
        name = appmod.name + "." + name
        if url_prefix and not url_prefix.startswith("/"):
            url_prefix = "/" + url_prefix
        module_url_prefix = (appmod.url_prefix + (url_prefix or "")) if appmod.url_prefix else url_prefix
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
            **opts,
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
        opts: Dict[str, Any] = {},
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
                opts=opts,
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
        **kwargs: Any,
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
            opts=kwargs,
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
        **kwargs: Any,
    ):
        super().__init__(
            app=app,
            name=name,
            import_name=import_name,
            static_folder=static_folder,
            static_path=static_path,
            url_prefix=url_prefix,
            hostname=hostname,
            cache=cache,
            root_path=root_path,
            pipeline=pipeline,
            **kwargs,
        )
        #: - `template_folder` is referred to application `template_path`
        #  - `template_path` is referred to module root_directory unless absolute
        self.template_folder = template_folder
        if template_path and not template_path.startswith("/"):
            template_path = os.path.join(self.root_path, template_path)
        self.template_path = template_path
        self._super_injectors = injectors or []
        self.injectors = []

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
        **kwargs,
    ) -> RoutingCtx:
        if name is not None and "." in name:
            raise RuntimeError("App modules' route names should not contains dots")
        name = self.name + "." + (name or "")
        pipeline = kwargs.get("pipeline", [])
        injectors = kwargs.get("injectors", [])
        if self.pipeline:
            pipeline = self.pipeline + pipeline
        kwargs["pipeline"] = pipeline
        if self.injectors:
            injectors = self.injectors + injectors
        kwargs["injectors"] = injectors
        kwargs["cache"] = kwargs.get("cache", self.cache)
        return self.app.route(
            paths=paths,
            name=name,
            template=template,
            prefix=self.url_prefix,
            template_folder=self.template_folder,
            template_path=self.template_path,
            hostname=self.hostname,
            **kwargs,
        )


class App(_App):
    __slots__ = ["cli", "template_default_extension", "template_path", "templater", "translator"]

    config_class = Config
    modules_class = AppModule
    signals_class = Signals
    test_client_class = EmmettTestClient

    def __init__(
        self,
        import_name: str,
        root_path: Optional[str] = None,
        url_prefix: Optional[str] = None,
        template_folder: str = "templates",
        config_folder: str = "config",
    ):
        super().__init__(
            import_name=import_name,
            root_path=root_path,
            url_prefix=url_prefix,
            config_folder=config_folder,
            template_folder=template_folder,
        )
        self.cli = click.Group(self.import_name)
        self.translator = Translator(
            os.path.join(self.root_path, "languages"),
            default_language=self.language_default or "en",
            watch_changes=self.debug,
            str_class=Tstr,
        )
        self.template_default_extension = ".html"
        self.templater: Templater = Templater(
            path=self.template_path,
            encoding=self.config.templates_encoding,
            escape=self.config.templates_escape,
            adjust_indent=self.config.templates_adjust_indent,
            reload=self.config.templates_auto_reload,
        )

    def _configure_paths(self, root_path, opts):
        if root_path is None:
            root_path = get_root_path(self.import_name)
        self.root_path = root_path
        self.static_path = os.path.join(self.root_path, "static")
        self.template_path = os.path.join(self.root_path, opts["template_folder"])
        self.config_path = os.path.join(self.root_path, opts["config_folder"])
        create_missing_app_folders(self, ["languages", "logs", "static"])

    def _init_routers(self, url_prefix):
        self._router_http = HTTPRouter(self, current, url_prefix=url_prefix)
        self._router_ws = WebsocketRouter(self, current, url_prefix=url_prefix)

    def _init_handlers(self):
        self._asgi_handlers["http"] = ASGIHTTPHandler(self, current)
        self._asgi_handlers["ws"] = ASGIWSHandler(self, current)
        self._rsgi_handlers["http"] = RSGIHTTPHandler(self, current)
        self._rsgi_handlers["ws"] = RSGIWSHandler(self, current)

    def _register_with_ctx(self):
        current.app = self

    @property
    def language_default(self) -> Optional[str]:
        return self._language_default

    @language_default.setter
    def language_default(self, value: str):
        self._language_default = value
        self.translator._update_config(self._language_default or "en")

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
        output: str = "auto",
    ) -> RoutingCtx:
        if callable(paths):
            raise SyntaxError("Use @route(), not @route.")
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
            output=output,
        )

    @property
    def command(self):
        return self.cli.command

    @property
    def command_group(self):
        return self.cli.group

    def make_shell_context(self, context):
        context["app"] = self
        return context

    def render_template(self, filename: str) -> str:
        ctx = {"current": current, "url": url, "asis": asis, "load_component": load_component}
        return self.templater.render(filename, ctx)

    def config_from_yaml(self, filename: str, namespace: Optional[str] = None):
        #: import configuration from yaml files
        rc = read_file(os.path.join(self.config_path, filename))
        rc = ymlload(rc, Loader=ymlLoader)
        c = self.config if namespace is None else self.config[namespace]
        for key, val in rc.items():
            c[key] = dict_to_sdict(val)

    #: Add a template extension to application
    def use_template_extension(self, ext_cls, **config):
        return self.templater.use_extension(ext_cls, **config)

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
        **kwargs: Any,
    ) -> AppModule:
        module_class = module_class or self.modules_class
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
            opts=kwargs,
        )

    def module_group(self, *modules: AppModule) -> AppModuleGroup:
        return AppModuleGroup(*modules)


class AppModuleGroup(_AppModuleGroup):
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
        **kwargs: Any,
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
            opts=kwargs,
        )

    def route(
        self,
        paths: Optional[Union[str, List[str]]] = None,
        name: Optional[str] = None,
        template: Optional[str] = None,
        **kwargs,
    ) -> RoutingCtxGroup:
        return RoutingCtxGroup([mod.route(paths=paths, name=name, template=template, **kwargs) for mod in self.modules])


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
