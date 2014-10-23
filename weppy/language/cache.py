# -*- coding: utf-8 -*-
"""
    weppy.language.cache
    --------------------

    Adapted from the web2py's code (http://www.web2py.com)

    :copyright: (c) by Massimo Di Pierro <mdipierro@cs.depaul.edu>
    :license: LGPLv3 (http://www.gnu.org/licenses/lgpl.html)
"""

from threading import RLock
from os import stat


language_cache = {}
_cfs = {}


def get_from_cache(filename, val, fun):
    lang_dict, lock = language_cache.get(
        filename, ({}, RLock()))
    lock.acquire()
    try:
        result = lang_dict.get(val)
    finally:
        lock.release()
    if result:
        return result
    lock.acquire()
    try:
        result = lang_dict.setdefault(val, fun())
    finally:
        lock.release()
    return result


def clear_cache(filename):
    cache = language_cache.setdefault(
        filename, ({}, RLock()))
    lang_dict, lock = cache
    lock.acquire()
    try:
        lang_dict.clear()
    finally:
        lock.release()


#: returns content from filename, making sure to close the file on exit.
def _read_file(filename, mode='r'):
    with open(filename, mode) as f:
        return f.read()


#: Caches the *filtered* file `filename` with `key` until the file is modified.
def getcfs(key, filename, filter=None):
    try:
        t = stat(filename).st_mtime
    except OSError:
        return filter() if callable(filter) else ''
    lock = RLock()
    lock.acquire()
    item = _cfs.get(key, None)
    lock.release()
    if item and item[0] == t:
        return item[1]
    if not callable(filter):
        data = _read_file(filename)
    else:
        data = filter()
    lock.acquire()
    _cfs[key] = (t, data)
    lock.release()
    return data
