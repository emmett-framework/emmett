# -*- coding: utf-8 -*-
"""
    weppy._reloader
    ---------------

    Provides auto-reloading utilities.

    :copyright: (c) 2014-2017 by Giovanni Barillari

    Adapted from werkzeug code (http://werkzeug.pocoo.org)
    :copyright: (c) 2015 by Armin Ronacher.

    :license: BSD, see LICENSE for more details.
"""

from __future__ import print_function
import os
import sys
import time
import subprocess
import threading
from itertools import chain

from ._compat import PY2, iteritems


def _iter_module_files(reloader_paths=None):
    """This iterates over all relevant Python files.  It goes through all
    loaded files from modules, all files in folders of already loaded modules
    as well as all files reachable through a package.
    """
    found = set()
    entered = set()

    def _verify_file(filename):
        if not filename:
            return
        filename = os.path.abspath(filename)
        old = None
        while not os.path.isfile(filename):
            old = filename
            filename = os.path.dirname(filename)
            if filename == old:
                break
        else:
            if filename[-4:] in ('.pyc', '.pyo'):
                filename = filename[:-1]
            if filename not in found:
                found.add(filename)
                return filename

    def _recursive_walk(path_entry):
        if path_entry in entered:
            return
        entered.add(path_entry)
        try:
            for filename in os.listdir(path_entry):
                path = os.path.join(path_entry, filename)
                if os.path.isdir(path):
                    for filename in _recursive_walk(path):
                        yield filename
                else:
                    if not filename.endswith(('.py', '.pyc', '.pyo')):
                        continue
                    filename = _verify_file(path)
                    if filename:
                        yield filename
        except OSError:
            pass

    if not reloader_paths:
        # The list call is necessary on Python 3 in case the module
        # dictionary modifies during iteration.
        for path_entry in list(sys.path):
            for filename in _recursive_walk(os.path.abspath(path_entry)):
                yield filename

        for module in list(sys.modules.values()):
            if module is None:
                continue
            filename = _verify_file(getattr(module, '__file__', None))
            if filename:
                yield filename
                for filename in _recursive_walk(os.path.dirname(filename)):
                    yield filename
            for package_path in getattr(module, '__path__', ()):
                for filename in _recursive_walk(os.path.abspath(package_path)):
                    yield filename
    else:
        for path_entry in reloader_paths:
            for filename in _recursive_walk(os.path.abspath(path_entry)):
                yield filename


def _find_common_roots(paths):
    """Out of some paths it finds the common roots that need monitoring."""
    paths = [x.split(os.path.sep) for x in paths]
    root = {}
    for chunks in sorted(paths, key=len, reverse=True):
        node = root
        for chunk in chunks:
            node = node.setdefault(chunk, {})
        node.clear()

    rv = set()

    def _walk(node, path):
        for prefix, child in iteritems(node):
            _walk(child, path + (prefix,))
        if not node:
            rv.add('/'.join(path))
    _walk(root, ())
    return rv


class ReloaderLoop(object):
    name = None

    # monkeypatched by testsuite. wrapping with `staticmethod` is required in
    # case time.sleep has been replaced by a non-c function (e.g. by
    # `eventlet.monkey_patch`) before we get here
    _sleep = staticmethod(time.sleep)

    def __init__(self, reloader_paths=None, extra_files=None, interval=1):
        self.reloader_paths = reloader_paths
        self.extra_files = set(os.path.abspath(x)
                               for x in extra_files or ())
        self.interval = interval

    def run(self):
        pass

    def restart_with_reloader(self):
        """Spawn a new Python interpreter with the same arguments as this one,
        but running the reloader thread.
        """
        while 1:
            #self.log('> Restarting (%s mode)' % self.name)
            print('> Restarting (%s mode)' % self.name)
            args = [sys.executable] + sys.argv
            new_environ = os.environ.copy()
            new_environ['WEPPY_RUN_MAIN'] = 'true'

            # a weird bug on windows. sometimes unicode strings end up in the
            # environment and subprocess.call does not like this, encode them
            # to latin1 and continue.
            if os.name == 'nt' and PY2:
                for key, value in iteritems(new_environ):
                    if isinstance(value, unicode):
                        new_environ[key] = value.encode('iso-8859-1')

            exit_code = subprocess.call(args, env=new_environ)
            if exit_code != 3:
                return exit_code

    def trigger_reload(self, filename):
        filename = os.path.abspath(filename)
        #self.log('> Detected change in %r, reloading' % filename)
        print('> Detected change in %r, reloading' % filename)
        sys.exit(3)


class StatReloaderLoop(ReloaderLoop):
    name = 'stat'

    def run(self):
        mtimes = {}
        while 1:
            for filename in chain(_iter_module_files(self.reloader_paths),
                                  self.extra_files):
                try:
                    mtime = os.stat(filename).st_mtime
                except OSError:
                    continue

                old_time = mtimes.get(filename)
                if old_time is None:
                    mtimes[filename] = mtime
                    continue
                elif mtime > old_time:
                    self.trigger_reload(filename)
            self._sleep(self.interval)


reloader_loops = {
    'stat': StatReloaderLoop,
}

reloader_loops['auto'] = reloader_loops['stat']


def run_with_reloader(app, host, port, extra_files=None, interval=1,
                      reloader_type='auto', reloader_paths=None):
    """Run the given function in an independent python interpreter."""
    import signal
    reloader = reloader_loops[reloader_type](reloader_paths, extra_files,
                                             interval)
    signal.signal(signal.SIGTERM, lambda *args: sys.exit(0))
    try:
        if os.environ.get('WEPPY_RUN_MAIN') == 'true':
            t = threading.Thread(target=app._run, args=(host, port))
            t.setDaemon(True)
            t.start()
            reloader.run()
        else:
            sys.exit(reloader.restart_with_reloader())
    except KeyboardInterrupt:
        pass
