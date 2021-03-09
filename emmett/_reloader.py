# -*- coding: utf-8 -*-
"""
    emmett._reloader
    ----------------

    Provides auto-reloading utilities.

    :copyright: 2014 Giovanni Barillari

    Adapted from werkzeug code (http://werkzeug.pocoo.org)
    :copyright: (c) 2015 by Armin Ronacher.

    :license: BSD-3-Clause
"""

import multiprocessing
import os
import signal
import subprocess
import ssl
import sys
import time

from itertools import chain
from typing import Optional

import click

from ._internal import locate_app
from .asgi.server import run as _asgi_run


def _iter_module_files():
    """This iterates over all relevant Python files.  It goes through all
    loaded files from modules, all files in folders of already loaded modules
    as well as all files reachable through a package.
    """
    for module in list(sys.modules.values()):
        if module is None:
            continue
        filename = getattr(module, '__file__', None)
        if filename:
            old = None
            while not os.path.isfile(filename):
                old = filename
                filename = os.path.dirname(filename)
                if filename == old:
                    break
            else:
                # if filename[-4:] in ('.pyc', '.pyo'):
                #     filename = filename[:-1]
                yield filename


def _get_args_for_reloading():
    """Returns the executable. This contains a workaround for windows
    if the executable is incorrectly reported to not have the .exe
    extension which can cause bugs on reloading.
    """
    rv = [sys.executable]
    py_script = sys.argv[0]
    if (
        os.name == 'nt' and not os.path.exists(py_script) and
        os.path.exists(py_script + '.exe')
    ):
        py_script += '.exe'
    if (
        os.path.splitext(rv[0])[1] == '.exe' and
        os.path.splitext(py_script)[1] == '.exe'
    ):
        rv.pop(0)
    rv.append(py_script)
    rv.extend(sys.argv[1:])
    return rv


class ReloaderLoop(object):
    name: str

    # monkeypatched by testsuite. wrapping with `staticmethod` is required in
    # case time.sleep has been replaced by a non-c function (e.g. by
    # `eventlet.monkey_patch`) before we get here
    _sleep = staticmethod(time.sleep)

    def __init__(self, extra_files=None, interval=1):
        self.extra_files = set(
            os.path.abspath(x) for x in extra_files or ())
        self.interval = interval

    def run(self):
        pass

    def restart_with_reloader(self):
        """Spawn a new Python interpreter with the same arguments as this one,
        but running the reloader thread.
        """
        while 1:
            click.secho('> Restarting (%s mode)' % self.name, fg='yellow')
            args = _get_args_for_reloading()
            new_environ = os.environ.copy()
            new_environ['EMMETT_RUN_MAIN'] = 'true'

            # a weird bug on windows. sometimes unicode strings end up in the
            # environment and subprocess.call does not like this, encode them
            # to latin1 and continue.
            # if os.name == 'nt' and PY2:
            #     for key, value in iteritems(new_environ):
            #         if isinstance(value, unicode):
            #             new_environ[key] = value.encode('iso-8859-1')

            exit_code = subprocess.call(args, env=new_environ)
            if exit_code != 3:
                return exit_code

    def trigger_reload(self, process, filename):
        filename = os.path.abspath(filename)
        click.secho('> Detected change in %r, reloading' % filename, fg='cyan')
        os.kill(process.pid, signal.SIGTERM)
        process.join()
        sys.exit(3)


class StatReloaderLoop(ReloaderLoop):
    name = 'stat'

    def run(self, process):
        mtimes = {}
        while 1:
            for filename in chain(_iter_module_files(), self.extra_files):
                try:
                    mtime = os.stat(filename).st_mtime
                except OSError:
                    continue

                old_time = mtimes.get(filename)
                if old_time is None:
                    mtimes[filename] = mtime
                    continue
                elif mtime > old_time:
                    self.trigger_reload(process, filename)
            self._sleep(self.interval)


reloader_loops = {
    'stat': StatReloaderLoop,
}

reloader_loops['auto'] = reloader_loops['stat']


def run_with_reloader(
    app_target,
    host,
    port,
    loop='auto',
    proto_http='auto',
    proto_ws='auto',
    log_level=None,
    access_log=None,
    ssl_certfile: Optional[str] = None,
    ssl_keyfile: Optional[str] = None,
    ssl_cert_reqs: int = ssl.CERT_NONE,
    ssl_ca_certs: Optional[str] = None,
    extra_files=None,
    interval=1,
    reloader_type='auto'
):
    reloader = reloader_loops[reloader_type](extra_files, interval)
    signal.signal(signal.SIGTERM, lambda *args: sys.exit(0))

    try:
        if os.environ.get('EMMETT_RUN_MAIN') == 'true':
            # FIXME: find a better way to have app files in stat checker
            locate_app(*app_target)

            process = multiprocessing.Process(
                target=_asgi_run,
                args=(app_target, host, port),
                kwargs={
                    "loop": loop,
                    "proto_http": proto_http,
                    "proto_ws": proto_ws,
                    "log_level": log_level,
                    "access_log": access_log,
                    "ssl_certfile": ssl_certfile,
                    "ssl_keyfile": ssl_keyfile,
                    "ssl_cert_reqs": ssl_cert_reqs,
                    "ssl_ca_certs": ssl_ca_certs
                }
            )
            process.start()
            reloader.run(process)
        else:
            sys.exit(reloader.restart_with_reloader())
    except KeyboardInterrupt:
        pass
