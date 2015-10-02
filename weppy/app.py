# -*- coding: utf-8 -*-
"""
    weppy.app
    ---------

    Provide the central application object.

    :copyright: (c) 2015 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

import sys
import os
import click
from yaml import load as ymlload
from ._compat import basestring
from ._internal import get_root_path, create_missing_app_folders
from .utils import dict_to_sdict
from .expose import Expose
from .datastructures import sdict, ConfigData
from .wsgi import error_handler
from .extensions import Extension, TemplateExtension
from .templating import render_template
from .utils import read_file


class App(object):
    debug = None

    def __init__(self, import_name, root_path=None,
                 template_folder='templates', config_folder='config'):
        self.import_name = import_name
        #: Set paths for the application
        if root_path is None:
            root_path = get_root_path(self.import_name)
        self.root_path = root_path
        self.static_path = os.path.join(self.root_path, "static")
        self.template_path = os.path.join(self.root_path, template_folder)
        self.config_path = os.path.join(self.root_path, config_folder)
        #: The click command line context for this application.
        self.cli = click.Group(self)
        #: Init the configuration
        self.config = ConfigData()
        self.config.hostname_default = None
        self.config.static_version = None
        self.config.static_version_urls = None
        self.config.url_default_namespace = None
        self.config.templates_auto_reload = False
        #: Trying to create needed folders
        create_missing_app_folders(self)
        #: init expose module
        Expose.application = self
        self.error_handlers = {}
        self.template_default_extension = '.html'
        #: init logger
        self._logger = None
        self.logger_name = self.import_name
        #: set request.now reference
        self.now_reference = "utc"
        #: init languages
        self.languages = []
        self.language_default = None
        self.language_force_on_url = False
        self.language_write = False
        #: init extensions
        self.ext = sdict()
        self._extensions_env = sdict()
        self.template_extensions = []
        self.template_preloaders = {}
        self.template_lexers = {}

    @property
    def name(self):
        """The name of the application. This is usually the import name
        with the difference that it's guessed from the run file if the
        import name is main.
        """
        if not hasattr(self, "_name"):
            if self.import_name == '__main__':
                fn = getattr(sys.modules['__main__'], '__file__', None)
                if fn is None:
                    self._name = '__main__'
                else:
                    self._name = os.path.splitext(os.path.basename(fn))[0]
            else:
                self._name = self.import_name
        return self._name

    @property
    def expose(self):
        return Expose

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
        return render_template(self, filename)

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

    #: Add an extension to application
    def use_extension(self, ext):
        if not issubclass(ext, Extension):
            raise RuntimeError('%s is an invalid weppy extension' %
                               ext.__name__)
        ext_env, ext_config = self.__init_extension(ext)
        self.ext[ext.__name__] = ext(self, ext_env, ext_config)
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

    def make_shell_context(self):
        """Returns the shell context for an interactive shell for this
        application.  This runs all the registered shell context
        processors.
        """
        #rv = {'app': self, 'g': g}
        rv = {'app': self}
        #for processor in self.shell_context_processors:
        #    rv.update(processor())
        return rv

    def _run(self, host, port):
        from .libs.rocket import Rocket
        r = Rocket((host, port), 'wsgi', {'wsgi_app': self})
        r.start()

    def run(self, host=None, port=None, reloader=True):
        if host is None:
            host = "127.0.0.1"
        if port is None:
            port = 8000
        self.debug = True
        if os.environ.get('WEPPY_RUN_MAIN') != 'true':
            quit_msg = "(press CTRL+C to quit)"
            self.log.info("> weppy application %s running on http://%s:%i %s" %
                          (self.import_name, host, port, quit_msg))
        if reloader:
            from ._reloader import run_with_reloader
            run_with_reloader(self, host, port)
        else:
            self._run(host, port)

    def wsgi_handler(self, environ, start_request):
        return error_handler(self, environ, start_request)

    def __call__(self, environ, start_request):
        return self.wsgi_handler(environ, start_request)


class AppModule(object):
    def __init__(self, app, name, import_name, template_folder=None,
                 template_path=None, url_prefix=None, hostname=None,
                 root_path=None):
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
            template_path = self.root_path+template_path
        self.template_path = template_path
        ## how to route static?
        ## and.. do we want this?? I think not..
        #if static_folder:
        #    self.static_folder = self.root_path+"/"+static_folder
        #if static_prefix:
        #    self.static_folder = self.app.static_folder+"/"+static_prefix
        self.url_prefix = url_prefix
        self.hostname = hostname
        self.common_handlers = []
        self.common_helpers = []

    def expose(self, path=None, name=None, template=None, **kwargs):
        if name is not None and "." in name:
            raise RuntimeError(
                "App modules' exposed names should not contains dots"
            )
        name = self.name+"."+(name or "")
        handlers = kwargs.get('handlers', [])
        helpers = kwargs.get('helpers', [])
        if self.common_handlers:
            handlers = self.common_handlers + handlers
        kwargs['handlers'] = handlers
        if self.common_helpers:
            helpers = self.common_helpers + helpers
        kwargs['helpers'] = helpers
        return self.app.expose(
            path=path, name=name, template=template, prefix=self.url_prefix,
            template_folder=self.template_folder,
            template_path=self.template_path, hostname=self.hostname, **kwargs)
