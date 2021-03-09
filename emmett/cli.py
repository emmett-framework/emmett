# -*- coding: utf-8 -*-
"""
    emmett.cli
    ---------

    Provide command line tools for Emmett applications.

    :copyright: 2014 Giovanni Barillari

    Based on the code of Flask (http://flask.pocoo.org)
    :copyright: (c) 2014 by Armin Ronacher.

    :license: BSD-3-Clause
"""

import code
import os
import re
import ssl
import sys
import types

import click

from .__version__ import __version__ as fw_version
from ._internal import locate_app, get_app_module
from .asgi.loops import loops
from .asgi.protocols import protocols_http, protocols_ws
from .asgi.server import run as asgi_run
from .logger import LOG_LEVELS


def find_app_module():
    rv, files, dirs = None, [], []
    for path in os.listdir():
        if any(path.startswith(val) for val in [".", "test"]):
            continue
        if os.path.isdir(path):
            if not path.startswith("_"):
                dirs.append(path)
            continue
        _, ext = os.path.splitext(path)
        if ext == ".py":
            files.append(path)
    if "app.py" in files:
        rv = "app.py"
    elif "app" in dirs:
        rv = "app"
    elif "__init__.py" in files:
        rv = "__init__.py"
    elif len(files) == 1:
        rv = files[0]
    elif len(dirs) == 1:
        rv = dirs[1]
    else:
        modules = []
        for path in dirs:
            if os.path.exists(os.path.join(path, "__init__.py")):
                modules.append(path)
        if len(modules) == 1:
            rv = modules[0]
    return rv


def find_db(module, var_name=None):
    #: Given a module instance this tries to find the database instances
    #  in the module.
    if var_name:
        return [getattr(module, var_name)]

    from .orm import Database

    matches = [
        v for k, v in module.__dict__.items() if isinstance(v, Database)
    ]
    return matches


def get_import_components(path):
    return (re.split(r":(?![\\/])", path, 1) + [None])[:2]


def prepare_import(path):
    #: Given a path this will try to calculate the python path, add it
    #  to the search path and return the actual module name that is expected.
    path = os.path.realpath(path)

    fname, ext = os.path.splitext(path)
    if ext == ".py":
        path = fname
    if os.path.basename(path) == "__init__":
        path = os.path.dirname(path)

    module_name = []

    #: move up untile outside package
    while True:
        path, name = os.path.split(path)
        module_name.append(name)

        if not os.path.exists(os.path.join(path, "__init__.py")):
            break

    if sys.path[0] != path:
        sys.path.insert(0, path)

    return ".".join(module_name[::-1])


class ScriptInfo(object):
    def __init__(self, app_import_path=None, debug=None):
        #: The application import path
        self.app_import_path = app_import_path or os.environ.get("EMMETT_APP")
        #: The debug flag. If this is not None, the application will
        #  automatically have it's debug flag overridden with this value.
        self.debug = debug
        #: A dictionary with arbitrary data that can be associated with
        #  this script info.
        self.data = {}
        self._loaded_app = None
        self._loaded_ctx = None
        self.db_var_name = None

    def _get_import_name(self):
        if self.app_import_path:
            path, name = get_import_components(self.app_import_path)
        else:
            path, name = (find_app_module(), None)
        return prepare_import(path) if path else None, name

    def load_app(self):
        if self._loaded_app is not None:
            return self._loaded_app

        import_name, app_name = self._get_import_name()
        app = locate_app(import_name, app_name) if import_name else None

        if app is None:
            raise RuntimeError("Could not locate an Emmett application.")

        if self.debug is not None:
            app.debug = self.debug

        self._loaded_app = app
        return app

    def load_appctx(self):
        ctx = {}
        import_name, _ = self._get_import_name()
        mod = get_app_module(import_name)

        for key in set(mod.__dict__.keys()) - {"__builtins__"}:
            value = mod.__dict__[key]
            if isinstance(value, types.FunctionType):
                continue
            ctx[key] = value

        self._loaded_ctx = ctx
        return ctx

    def load_db(self):
        import_name, _ = self._get_import_name()
        mod = get_app_module(import_name)
        return find_db(mod, self.db_var_name)


pass_script_info = click.make_pass_decorator(ScriptInfo)


def set_app_value(ctx, param, value):
    ctx.ensure_object(ScriptInfo).app_import_path = value


app_option = click.Option(
    ['-a', '--app'],
    help='The application to run',
    callback=set_app_value,
    is_eager=True
)


class EmmettGroup(click.Group):
    def __init__(
        self,
        add_default_commands=True,
        add_app_option=True,
        add_debug_option=True,
        **extra
    ):
        params = list(extra.pop('params', None) or ())
        if add_app_option:
            params.append(app_option)
        #if add_debug_option:
        #    params.append(debug_option)

        click.Group.__init__(self, params=params, **extra)
        #self.create_app = create_app

        if add_default_commands:
            self.add_command(develop_command)
            self.add_command(shell_command)
            self.add_command(routes_command)
            self.add_command(serve_command)

    def list_commands(self, ctx):
        rv = super(EmmettGroup, self).list_commands(ctx)
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
        return super().main(*args, **kwargs)


@click.command('develop', short_help='Runs a development server.')
@click.option(
    '--host', '-h', default='127.0.0.1', help='The interface to bind to.')
@click.option(
    '--port', '-p', type=int, default=8000, help='The port to bind to.')
@click.option(
    '--loop', type=click.Choice(loops.keys()), default='auto',
    help='Event loop implementation.')
@click.option(
    '--http-protocol', type=click.Choice(protocols_http.keys()),
    default='auto', help='HTTP protocol implementation.')
@click.option(
    '--ws-protocol', type=click.Choice(protocols_ws.keys()),
    default='auto', help='Websocket protocol implementation.')
@click.option(
    '--ssl-certfile', type=str, default=None, help='SSL certificate file')
@click.option(
    '--ssl-keyfile', type=str, default=None, help='SSL key file')
@click.option(
    '--ssl-cert-reqs', type=int, default=ssl.CERT_NONE,
    help='Whether client certificate is required (see ssl module)')
@click.option(
    '--ssl-ca-certs', type=str, default=None, help='CA certificates file')
@click.option(
    '--reloader/--no-reloader', is_flag=True, default=True,
    help='Runs with reloader.')
@pass_script_info
def develop_command(
    info, host, port,
    loop, http_protocol, ws_protocol,
    ssl_certfile, ssl_keyfile, ssl_cert_reqs, ssl_ca_certs,
    reloader
):
    os.environ["EMMETT_RUN_ENV"] = 'true'
    app_target = info._get_import_name()

    if os.environ.get('EMMETT_RUN_MAIN') != 'true':
        click.echo(
            ' '.join([
                "> Starting Emmett development server on app",
                click.style(app_target[0], fg="cyan", bold=True)
            ])
        )
        click.echo(
            ' '.join([
                click.style("> Emmett application", fg="green"),
                click.style(app_target[0], fg="cyan", bold=True),
                click.style("running on", fg="green"),
                click.style(f"http://{host}:{port}", fg="cyan"),
                click.style("(press CTRL+C to quit)", fg="green")
            ])
        )

    if reloader:
        from ._reloader import run_with_reloader
        runner = run_with_reloader
    else:
        runner = asgi_run

    runner(
        app_target,
        host,
        port,
        loop=loop,
        proto_http=http_protocol,
        proto_ws=ws_protocol,
        log_level='debug',
        access_log=True,
        ssl_certfile=ssl_certfile,
        ssl_keyfile=ssl_keyfile,
        ssl_cert_reqs=ssl_cert_reqs,
        ssl_ca_certs=ssl_ca_certs
    )


@click.command('serve', short_help='Serve the app.')
@click.option(
    '--host', '-h', default='0.0.0.0', help='The interface to bind to.')
@click.option(
    '--port', '-p', type=int, default=8000, help='The port to bind to.')
@click.option(
    "--workers", type=int, default=1, help="Number of worker processes. Defaults to 1.")
@click.option(
    '--loop', type=click.Choice(loops.keys()), default='auto',
    help='Event loop implementation.')
@click.option(
    '--http-protocol', type=click.Choice(protocols_http.keys()),
    default='auto', help='HTTP protocol implementation.')
@click.option(
    '--ws-protocol', type=click.Choice(protocols_ws.keys()),
    default='auto', help='Websocket protocol implementation.')
@click.option(
    '--log-level', type=click.Choice(LOG_LEVELS.keys()), default='info',
    help='Logging level.')
@click.option(
    '--access-log/--no-access-log', is_flag=True, default=True,
    help='Enable/Disable access log.')
@click.option(
    '--proxy-headers/--no-proxy-headers', is_flag=True, default=False,
    help='Enable/Disable proxy headers.')
@click.option(
    '--proxy-trust-ips', type=str, default=None,
    help='Comma seperated list of IPs to trust with proxy headers')
@click.option(
    '--max-concurrency', type=int,
    help='The maximum number of concurrent connections.')
@click.option(
    '--backlog', type=int, default=2048,
    help='Maximum number of connections to hold in backlog')
@click.option(
    '--keep-alive-timeout', type=int, default=0,
    help='Keep alive timeout for connections.')
@click.option(
    '--ssl-certfile', type=str, default=None, help='SSL certificate file')
@click.option(
    '--ssl-keyfile', type=str, default=None, help='SSL key file')
@click.option(
    '--ssl-cert-reqs', type=int, default=ssl.CERT_NONE,
    help='Whether client certificate is required (see ssl module)')
@click.option(
    '--ssl-ca-certs', type=str, default=None, help='CA certificates file')
@pass_script_info
def serve_command(
    info, host, port, workers,
    loop, http_protocol, ws_protocol,
    log_level, access_log,
    proxy_headers, proxy_trust_ips,
    max_concurrency, backlog, keep_alive_timeout,
    ssl_certfile, ssl_keyfile, ssl_cert_reqs, ssl_ca_certs
):
    app_target = info._get_import_name()
    asgi_run(
        app_target,
        host=host, port=port,
        loop=loop, proto_http=http_protocol, proto_ws=ws_protocol,
        log_level=log_level, access_log=access_log,
        proxy_headers=proxy_headers, proxy_trust_ips=proxy_trust_ips,
        workers=workers,
        limit_concurrency=max_concurrency,
        backlog=backlog,
        timeout_keep_alive=keep_alive_timeout,
        ssl_certfile=ssl_certfile,
        ssl_keyfile=ssl_keyfile,
        ssl_cert_reqs=ssl_cert_reqs,
        ssl_ca_certs=ssl_ca_certs
    )


@click.command('shell', short_help='Runs a shell in the app context.')
@pass_script_info
def shell_command(info):
    os.environ['EMMETT_CLI_ENV'] = 'true'
    ctx = info.load_appctx()
    app = info.load_app()
    banner = 'Python %s on %s\nEmmett %s shell on app: %s' % (
        sys.version,
        sys.platform,
        fw_version,
        app.import_name
    )
    code.interact(banner=banner, local=app.make_shell_context(ctx))


@click.command('routes', short_help='Display the app routing table.')
@pass_script_info
def routes_command(info):
    app = info.load_app()
    click.echo(
        "".join([
            "> Routing table for Emmett application ",
            click.style(app.import_name, fg="cyan", bold=True),
            ":"
        ])
    )
    for route in app._router_http._routes_str.values():
        click.echo(route)
    for route in app._router_ws._routes_str.values():
        click.echo(route)


cli = EmmettGroup(help="")


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
    cli.main(prog_name="python -m emmett" if as_module else None)


if __name__ == '__main__':
    main(as_module=True)
