# -*- coding: utf-8 -*-

import multiprocessing
import os
import signal
import sys
import time

from itertools import chain

HANDLED_SIGNALS = {
    signal.SIGINT,
    signal.SIGTERM
}


class Reloader(object):
    _sleep = staticmethod(time.sleep)

    def __init__(self, extra_files=None, interval=1):
        # self.logger = logger
        self.should_exit = False
        self.mtimes = {}
        self.extra_files = set(
            os.path.abspath(x) for x in extra_files or ())
        self.interval = interval

    def handle_exit(self, sig, frame):
        self.should_exit = True

    def run(self, target, kwargs):
        pid = os.getpid()

        print("> Starting reloader process [{}]".format(pid))

        for sig in HANDLED_SIGNALS:
            signal.signal(sig, self.handle_exit)

        process = multiprocessing.Process(target=target, kwargs=kwargs)
        process.start()

        while process.is_alive() and not self.should_exit:
            time.sleep(self.interval)
            if self.should_restart():
                self.clear()
                os.kill(process.pid, signal.SIGTERM)
                process.join()
                process = multiprocessing.Process(target=target, kwargs=kwargs)
                process.start()

        print("Stopping reloader process [{}]".format(pid))

        sys.exit(process.exitcode)

    def clear(self):
        self.mtimes = {}

    def should_restart(self):
        for filename in chain(_iter_module_files(), self.extra_files):
            try:
                mtime = os.stat(filename).st_mtime
            except OSError as exc:
                continue

            old_time = self.mtimes.get(filename)
            if old_time is None:
                self.mtimes[filename] = mtime
                continue
            elif mtime > old_time:
                print(
                    '> Detected change in %r, reloading' %
                    os.path.abspath(filename)
                )
                return True
        return False


def _iter_module_files():
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
                yield filename
