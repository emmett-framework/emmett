# -*- coding: utf-8 -*-
"""
    weppy.cli
    ---------

    Provide command line tools for weppy applications.

    :copyright: (c) 2015 by Giovanni Barillari

    Based on the code of Flask (http://flask.pocoo.org)
    :copyright: (c) 2014 by Armin Ronacher.

    :license: BSD, see LICENSE for more details.
"""

from __future__ import print_function
import os
import sys
import click
from ._compat import iteritems


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
    matches = [v for k, v in iteritems(module.__dict__)
               if isinstance(v, App)]

    if len(matches) == 1:
        return matches[0]
    raise Exception(
        'Failed to find application in module "%s".' % module.__name__
    )


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
        raise 'The file provided (%s) does is not a valid Python file.'
    filename = os.path.realpath(filename)

    dirpath = filename
    while 1:
        dirpath, extra = os.path.split(dirpath)
        module.append(extra)
        if not os.path.isfile(os.path.join(dirpath, '__init__.py')):
            break

    sys.path.insert(0, dirpath)
    return '.'.join(module[::-1])


def locate_app(app_id):
    """Attempts to locate the application."""
    if ':' in app_id:
        module, app_obj = app_id.split(':', 1)
    else:
        module = app_id
        app_obj = None

    __import__(module)
    mod = sys.modules[module]
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
        #: The debug flag.  If this is not None, the application will
        #: automatically have it's debug flag overridden with this value.
        self.debug = debug
        #: A dictionary with arbitrary data that can be associated with
        #: this script info.
        self.data = {}
        self._loaded_app = None

    def load_app(self):
        """Loads the app (if not yet loaded) and returns it.  Calling
        this multiple times will just result in the already loaded app to
        be returned.
        """
        if self._loaded_app is not None:
            return self._loaded_app
        if self.app_import_path is None:
            raise "Could not locate application."
        a = locate_app(self.app_import_path)
        if self.debug is not None:
            a.debug = self.debug
        self._loaded_app = a
        return a


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
        except:
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
@click.option('--reloader', default=True, help='Runs with reloader.')
@pass_script_info
def run_command(info, host, port, reloader):
    app = info.load_app()
    app.debug = True
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
    app = info.load_app()
    banner = 'Python %s on %s\nweppy shell on app: %s' % (
        sys.version,
        sys.platform,
        app.import_name
        #app.debug and ' [debug]' or '',
        #app.instance_path,
    )
    code.interact(banner=banner, local=app.make_shell_context())


cli = WeppyGroup(help="")


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
