# -*- coding: utf-8 -*-
"""
    weppy.app
    ---------

    Provides the central application object.

    :copyright: (c) 2014-2017 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

import sys
import os
import click
from yaml import load as ymlload
from ._compat import basestring
from ._internal import (
    get_root_path, create_missing_app_folders, warn_of_deprecation
)
from .datastructures import sdict, ConfigData
from .expose import Expose, url
from .extensions import Extension, TemplateExtension
from .globals import current
from .templating.core import Templater
from .utils import dict_to_sdict, cachedprop, read_file
from .wsgi import (
    error_handler, static_handler, dynamic_handler,
    _nolang_static_handler, _lang_static_handler
)


class App(object):
    debug = None
    test_client_class = None

    def __init__(
        self, import_name, root_path=None, template_folder='templates',
        config_folder='config'
    ):
        self.import_name = import_name
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
        self.config = ConfigData()
        self.config.modules_class = AppModule
        self.config.hostname_default = None
        self.config.static_version = None
        self.config.static_version_urls = None
        self.config.handle_static = True
        self.config.url_default_namespace = None
        self.config.templates_auto_reload = False
        self.config.templates_escape = 'common'
        #: try to create needed folders
        create_missing_app_folders(self)
        #: init expose module
        Expose.application = self
        self.error_handlers = {}
        self.template_default_extension = '.html'
        #: init logger
        self._logger = None
        self.logger_name = self.import_name
        #: init languages
        self.languages = []
        self.language_default = None
        self.language_force_on_url = False
        self.language_write = False
        #: init extensions
        self.ext = sdict()
        self._extensions_env = sdict()
        self._extensions_listeners = {key: [] for key in Extension._signals_}
        self.template_extensions = []
        self.template_preloaders = {}
        self.template_lexers = {}
        #: init templater
        self.templater = Templater(self)
        #: init debug var
        self.debug = os.environ.get('WEPPY_RUN_ENV') == "true"

    @cachedprop
    def name(self):
        """The name of the application. This is usually the import name
        with the difference that it's guessed from the run file if the
        import name is main.
        """
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
    def route(self):
        return Expose

    @property
    def pipeline(self):
        return self.route._pipeline

    @pipeline.setter
    def pipeline(self, pipes):
        self.route._pipeline = pipes

    @property
    def injectors(self):
        return self.route._injectors

    @injectors.setter
    def injectors(self, injectors):
        self.route._injectors = injectors

    #: 1.0 deprecations
    @property
    def common_handlers(self):
        warn_of_deprecation('common_handlers', 'pipeline', 'App', 3)
        return self.pipeline

    @common_handlers.setter
    def common_handlers(self, handlers):
        warn_of_deprecation('common_handlers', 'pipeline', 'App', 3)
        self.pipeline = handlers

    @property
    def common_helpers(self):
        warn_of_deprecation('common_helpers', 'injectors', 'App', 3)
        return self.injectors

    @common_helpers.setter
    def common_helpers(self, helpers):
        warn_of_deprecation('common_helpers', 'injectors', 'App', 3)
        self.injectors = helpers
    #/

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
        ctx = {'current': current, 'url': url}
        return self.templater.render(self.template_path, filename, ctx)

    def config_from_yaml(self, filename, namespace=None):
        #: import configuration from yaml files
        rc = read_file(os.path.join(self.config_path, filename))
        rc = ymlload(rc)
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
    def use_extension(self, ext):
        if not issubclass(ext, Extension):
            raise RuntimeError('%s is an invalid weppy extension' %
                               ext.__name__)
        ext_env, ext_config = self.__init_extension(ext)
        self.ext[ext.__name__] = ext(self, ext_env, ext_config)
        self.__register_extension_listeners(self.ext[ext.__name__])
        self.ext[ext.__name__].on_load()

    #: Add a template extension to application
    def add_template_extension(self, ext):
        if not issubclass(ext, TemplateExtension):
            raise RuntimeError('%s is an invalid weppy template extension' %
                               ext.__name__)
        ext_env, ext_config = self.__init_extension(ext)
        self.template_extensions.append(ext(ext_env, ext_config))
        fext = self.template_extensions[-1].file_extension
        if fext is not None and isinstance(fext, basestring):
            if fext not in self.template_preloaders.keys():
                self.template_preloaders[fext] = []
            self.template_preloaders[fext].append(self.template_extensions[-1])
        lexers = self.template_extensions[-1].lexers
        for name, lexer in lexers.items():
            self.template_lexers[name] = lexer(self.template_extensions[-1])

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

    def _run(self, host, port):
        from .libs.rocket import Rocket
        r = Rocket((host, port), 'wsgi', {'wsgi_app': self})
        r.start()

    def run(self, host=None, port=None, reloader=True, debug=True):
        if host is None:
            host = "127.0.0.1"
        if port is None:
            port = 8000
        self.debug = debug
        if os.environ.get('WEPPY_RUN_MAIN') != 'true':
            quit_msg = "(press CTRL+C to quit)"
            self.log.info("> weppy application %s running on http://%s:%i %s" %
                          (self.import_name, host, port, quit_msg))
        if reloader:
            from ._reloader import run_with_reloader
            run_with_reloader(self, host, port)
        else:
            self._run(host, port)

    def test_client(self, use_cookies=True, **kwargs):
        tclass = self.test_client_class
        if tclass is None:
            from .testing import WeppyTestClient
            tclass = WeppyTestClient
        return tclass(self, use_cookies=use_cookies, **kwargs)

    @cachedprop
    def common_static_handler(self):
        if self.config.handle_static:
            return static_handler
        return dynamic_handler

    @cachedprop
    def static_handler(self):
        if self.language_force_on_url:
            return _lang_static_handler
        return _nolang_static_handler

    def wsgi_handler(self, environ, start_request):
        return error_handler(self, environ, start_request)

    def __call__(self, environ, start_request):
        return self.wsgi_handler(environ, start_request)

    def module(
        self, import_name, name, template_folder=None, template_path=None,
        url_prefix=None, hostname=None, root_path=None, module_class=None
    ):
        module_class = module_class or self.config.modules_class
        return module_class.from_app(
            self, import_name, name, template_folder, template_path,
            url_prefix, hostname, root_path
        )


class AppModule(object):
    @classmethod
    def from_app(
        cls, app, import_name, name, template_folder, template_path,
        url_prefix, hostname, root_path
    ):
        return cls(
            app, name, import_name, template_folder, template_path, url_prefix,
            hostname, root_path
        )

    @classmethod
    def from_module(
        cls, appmod, import_name, name, template_folder, template_path,
        url_prefix, hostname, root_path
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
        return cls(
            appmod.app, name, import_name, template_folder, template_path,
            module_url_prefix, hostname, root_path, pipeline=appmod.pipeline,
            injectors=appmod.injectors
        )

    def module(
        self, import_name, name, template_folder=None, template_path=None,
        url_prefix=None, hostname=None, root_path=None, module_class=None
    ):
        module_class = module_class or self.__class__
        return module_class.from_module(
            self, import_name, name, template_folder, template_path,
            url_prefix, hostname, root_path
        )

    def __init__(
        self, app, name, import_name, template_folder=None, template_path=None,
        url_prefix=None, hostname=None, root_path=None, pipeline=[],
        injectors=[]
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

    #: 1.0 deprecations
    @property
    def common_handlers(self):
        warn_of_deprecation('common_handlers', 'pipeline', 'AppModule', 3)
        return self.pipeline

    @common_handlers.setter
    def common_handlers(self, handlers):
        warn_of_deprecation('common_handlers', 'pipeline', 'AppModule', 3)
        self.pipeline = handlers

    @property
    def common_helpers(self):
        warn_of_deprecation('common_helpers', 'injectors', 'AppModule', 3)
        return self.injectors

    @common_helpers.setter
    def common_helpers(self, helpers):
        warn_of_deprecation('common_helpers', 'injectors', 'AppModule', 3)
        self.injectors = helpers
    #/

    def route(self, paths=None, name=None, template=None, **kwargs):
        if name is not None and "." in name:
            raise RuntimeError(
                "App modules' route names should not contains dots"
            )
        name = self.name + "." + (name or "")
        #: 1.0 deprecations
        if 'handlers' in kwargs:
            warn_of_deprecation('handlers', 'pipeline', 'route', 3)
            kwargs['pipeline'] = kwargs['handlers']
            del kwargs['handlers']
        if 'helpers' in kwargs:
            warn_of_deprecation('helpers', 'injectors', 'route', 3)
            kwargs['injectors'] = kwargs['helpers']
            del kwargs['helpers']
        #/
        pipeline = kwargs.get('pipeline', [])
        injectors = kwargs.get('injectors', [])
        if self.pipeline:
            pipeline = self.pipeline + pipeline
        kwargs['pipeline'] = pipeline
        if self.injectors:
            injectors = self.injectors + injectors
        kwargs['injectors'] = injectors
        return self.app.route(
            paths=paths, name=name, template=template, prefix=self.url_prefix,
            template_folder=self.template_folder,
            template_path=self.template_path, hostname=self.hostname, **kwargs)
