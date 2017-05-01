# -*- coding: utf-8 -*-
"""
    weppy.cli
    ---------

    Provide command line tools for weppy applications.

    :copyright: (c) 2014-2017 by Giovanni Barillari

    Based on the code of Flask (http://flask.pocoo.org)
    :copyright: (c) 2014 by Armin Ronacher.

    :license: BSD, see LICENSE for more details.
"""

from __future__ import print_function

import click
import os
import sys
import types
from ._compat import itervalues, iteritems
from . import __version__ as weppy_version


def find_best_app(module):
    """Given a module instance this tries to find the best possible
    application in the module or raises an exception.
    """
    from .app import App

    # Search for the most common names first.
    for attr_name in 'app', 'application':
        app = getattr(module, attr_name, None)
        if app is not None and isinstance(app, App):
            return app

    # Otherwise find the only object that is a weppy App instance.
    matches = [v for k, v in iteritems(module.__dict__) if isinstance(v, App)]

    if len(matches) == 1:
        return matches[0]
    raise Exception(
        'Failed to find application in module "%s".' % module.__name__
    )


def find_db(module, var_name=None):
    #: Given a module instance this tries to find the database instances
    #  in the module.
    if var_name:
        return [getattr(module, var_name)]
    from .orm import Database
    matches = [
        v for k, v in iteritems(module.__dict__) if isinstance(v, Database)]

    return matches


def prepare_exec_for_file(filename):
    """Given a filename this will try to calculate the python path, add it
    to the search path and return the actual module name that is expected.
    """
    module = []

    # Chop off file extensions or package markers
    if filename.endswith('.py'):
        filename = filename[:-3]
    elif os.path.split(filename)[1] == '__init__.py':
        filename = os.path.dirname(filename)
    else:
        raise Exception(
            'The file provided (%s) does is not a valid Python file.')
    filename = os.path.realpath(filename)

    dirpath = filename
    while 1:
        dirpath, extra = os.path.split(dirpath)
        module.append(extra)
        if not os.path.isfile(os.path.join(dirpath, '__init__.py')):
            break

    sys.path.insert(0, dirpath)
    return '.'.join(module[::-1])


def get_app_module(app_id):
    if ':' in app_id:
        module, app_obj = app_id.split(':', 1)
    else:
        module = app_id
        app_obj = None
    mod = sys.modules.get(module)
    if mod is None:
        __import__(module)
        mod = sys.modules[module]
    return module, mod, app_obj


def locate_app(app_id):
    """Attempts to locate the application."""
    module, mod, app_obj = get_app_module(app_id)
    if app_obj is None:
        app = find_best_app(mod)
    else:
        app = getattr(mod, app_obj, None)
        if app is None:
            raise RuntimeError('Failed to find application in module "%s"'
                               % module)
    return app


class ScriptInfo(object):
    """Help object to deal with Weppy applications.  This is usually not
    necessary to interface with as it's used internally in the dispatching
    to click.
    """

    def __init__(self, app_import_path=None, debug=None):
        #: The application import path
        self.app_import_path = app_import_path
        #: The debug flag. If this is not None, the application will
        #: automatically have it's debug flag overridden with this value.
        self.debug = debug
        #: A dictionary with arbitrary data that can be associated with
        #: this script info.
        self.data = {}
        self._loaded_ctx = None
        self._loaded_app = None
        self.db_var_name = None
        #: Set environment flag
        os.environ['WEPPY_CLI_ENV'] = 'true'

    def load_appctx(self):
        if self._loaded_ctx is not None:
            return self._loaded_ctx
        if self.app_import_path is None:
            raise Exception("Could not locate application.")
        module, mod, app_obj = get_app_module(self.app_import_path)
        ctx = {}
        for key, value in iteritems(mod.__dict__):
            if key == "__builtins__" or isinstance(value, types.FunctionType):
                continue
            ctx[key] = value
        self._loaded_ctx = ctx
        return ctx

    def load_app(self):
        """Loads the app (if not yet loaded) and returns it.  Calling
        this multiple times will just result in the already loaded app to
        be returned.
        """
        if self._loaded_app is not None:
            return self._loaded_app
        if self.app_import_path is None:
            raise Exception("Could not locate application.")
        a = locate_app(self.app_import_path)
        if self.debug is not None:
            a.debug = self.debug
        self._loaded_app = a
        return a

    def load_db(self):
        if self.app_import_path is None:
            raise Exception("Could not locate application.")
        module, mod, app_obj = get_app_module(self.app_import_path)
        return find_db(mod, self.db_var_name)


pass_script_info = click.make_pass_decorator(ScriptInfo)


def set_app_value(ctx, param, value):
    if value is not None:
        if os.path.isfile(value):
            value = prepare_exec_for_file(value)
        elif '.' not in sys.path:
            sys.path.insert(0, '.')
    ctx.ensure_object(ScriptInfo).app_import_path = value


app_option = click.Option(
    ['-a', '--app'],
    help='The application to run',
    callback=set_app_value, is_eager=True
)


class WeppyGroup(click.Group):
    def __init__(self, add_default_commands=True, add_app_option=True,
                 add_debug_option=True, **extra):
        params = list(extra.pop('params', None) or ())
        if add_app_option:
            params.append(app_option)
        #if add_debug_option:
        #    params.append(debug_option)

        click.Group.__init__(self, params=params, **extra)
        #self.create_app = create_app

        if add_default_commands:
            self.add_command(run_command)
            self.add_command(shell_command)
            self.add_command(routes_command)

    def list_commands(self, ctx):
        rv = super(WeppyGroup, self).list_commands(ctx)
        info = ctx.ensure_object(ScriptInfo)
        try:
            rv = rv + info.load_app().cli.list_commands(ctx)
        except Exception:
            pass
        return rv

    def get_command(self, ctx, name):
        # We load built-in commands first as these should always be the
        # same no matter what the app does.  If the app does want to
        # override this it needs to make a custom instance of this group
        # and not attach the default commands.
        #
        # This also means that the script stays functional in case the
        # application completely fails.
        rv = click.Group.get_command(self, ctx, name)
        if rv is not None:
            return rv

        info = ctx.ensure_object(ScriptInfo)
        try:
            rv = info.load_app().cli.get_command(ctx, name)
            if rv is not None:
                return rv
        except Exception:
            pass

    def main(self, *args, **kwargs):
        obj = kwargs.get('obj')
        if obj is None:
            obj = ScriptInfo()
        kwargs['obj'] = obj
        return click.Group.main(self, *args, **kwargs)


@click.command('run', short_help='Runs a development server.')
@click.option('--host', '-h', default='127.0.0.1',
              help='The interface to bind to.')
@click.option('--port', '-p', default=8000,
              help='The port to bind to.')
@click.option('--reloader', type=(bool), default=True,
              help='Runs with reloader.')
@click.option('--debug', type=(bool), default=True, help='Runs in debug mode.')
@pass_script_info
def run_command(info, host, port, reloader, debug):
    os.environ["WEPPY_RUN_ENV"] = 'true'
    app = info.load_app()
    app.debug = debug
    if os.environ.get('WEPPY_RUN_MAIN') != 'true':
        print("> Serving weppy application %s" % app.import_name)
        quit_msg = "(press CTRL+C to quit)"
        print("> weppy application %s running on http://%s:%i %s" %
              (app.import_name, host, port, quit_msg))
    if reloader:
        from ._reloader import run_with_reloader
        run_with_reloader(app, host, port)
    else:
        app._run(host, port)


@click.command('shell', short_help='Runs a shell in the app context.')
@pass_script_info
def shell_command(info):
    import code
    ctx = info.load_appctx()
    app = info.load_app()
    banner = 'Python %s on %s\nweppy %s shell on app: %s' % (
        sys.version,
        sys.platform,
        weppy_version,
        app.import_name
    )
    code.interact(banner=banner, local=app.make_shell_context(ctx))


@click.command('routes', short_help='Display the app routing table.')
@pass_script_info
def routes_command(info):
    app = info.load_app()
    print("> Routing table for weppy application %s:" % app.import_name)
    for route in itervalues(app.route._routes_str):
        print(route)


cli = WeppyGroup(help="")


def set_db_value(ctx, param, value):
    ctx.ensure_object(ScriptInfo).db_var_name = value


@cli.group('migrations', short_help='Runs migration operations.')
@click.option(
    '--db', help='The db instance to use', callback=set_db_value,
    is_eager=True)
def migrations_cli(db):
    pass


@migrations_cli.command(
    'status', short_help='Shows current database revision.')
@click.option('--verbose', '-v', default=False, is_flag=True)
@pass_script_info
def migrations_status(info, verbose):
    from .orm.migrations.commands import status
    app = info.load_app()
    dbs = info.load_db()
    status(app, dbs, verbose)


@migrations_cli.command('history', short_help="Shows migrations history.")
@click.option('--range', '-r', default=None)
@click.option('--verbose', '-v', default=False, is_flag=True)
@pass_script_info
def migrations_history(info, range, verbose):
    from .orm.migrations.commands import history
    app = info.load_app()
    dbs = info.load_db()
    history(app, dbs, range, verbose)


@migrations_cli.command(
    'generate', short_help='Generate a new migration from application models.')
@click.option('--message', '-m', default='Generated migration',
              help='The description for the new migration.')
@click.option('-head', default='head', help='The migration to generate from')
@pass_script_info
def migrations_generate(info, message, head):
    from .orm.migrations.commands import generate
    app = info.load_app()
    dbs = info.load_db()
    generate(app, dbs, message, head)


@migrations_cli.command('new', short_help='Generate a new empty migration.')
@click.option('--message', '-m', default='New migration',
              help='The description for the new migration.')
@click.option('-head', default='head', help='The migration to generate from')
@pass_script_info
def migrations_new(info, message, head):
    from .orm.migrations.commands import new
    app = info.load_app()
    dbs = info.load_db()
    new(app, dbs, message, head)


@migrations_cli.command(
    'up', short_help='Upgrades the database to the selected migration.')
@click.option('--revision', '-r', default='head',
              help='The migration to upgrade to.')
@pass_script_info
def migrations_up(info, revision):
    from .orm.migrations.commands import up
    app = info.load_app()
    dbs = info.load_db()
    up(app, dbs, revision)


@migrations_cli.command(
    'down', short_help='Downgrades the database to the selected migration.')
@click.option('--revision', '-r', required=True,
              help='The migration to downgrade to.')
@pass_script_info
def migrations_down(info, revision):
    from .orm.migrations.commands import down
    app = info.load_app()
    dbs = info.load_db()
    down(app, dbs, revision)


def main(as_module=False):
    this_module = __package__ + '.cli'
    args = sys.argv[1:]

    if as_module:
        if sys.version_info >= (2, 7):
            name = 'python -m ' + this_module.rsplit('.', 1)[0]
        else:
            name = 'python -m ' + this_module

        # This module is always executed as "python -m run" and as such
        # we need to ensure that we restore the actual command line so that
        # the reloader can properly operate.
        sys.argv = ['-m', this_module] + sys.argv[1:]
    else:
        name = None

    cli.main(args=args, prog_name=name)


if __name__ == '__main__':
    main(as_module=True)
