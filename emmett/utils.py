# -*- coding: utf-8 -*-
"""
    emmett.utils
    ------------

    Provides some utilities for Emmett.

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

import asyncio
import pendulum
import re
import socket

from datetime import datetime, date, time
from pendulum.parsing import _parse as _pendulum_parse

from .datastructures import sdict


def cachedprop(fget, doc=None, name=None):
    doc = doc or fget.__doc__
    name = name or fget.__name__
    if asyncio.iscoroutinefunction(fget):
        return _cached_prop_loop(fget, doc, name)
    return _cached_prop_sync(fget, doc, name)


class _cached_prop(object):
    def __init__(self, fget, doc, name):
        self.fget = fget
        self.__doc__ = doc
        self.__name__ = name


class _cached_prop_sync(_cached_prop):
    def __get__(self, obj, cls):
        if obj is None:
            return self
        obj.__dict__[self.__name__] = rv = self.fget(obj)
        return rv


class _cached_awaitable_coro(object):
    slots = ['coro_f', 'obj', '_result', '_awaitable']

    def __init__(self, coro_f, obj):
        self.coro_f = coro_f
        self.obj = obj
        self._awaitable = self.__fetcher

    async def __fetcher(self):
        self._result = rv = await self.coro_f(self.obj)
        self._awaitable = self.__cached
        return rv

    async def __cached(self):
        return self._result

    def __await__(self):
        return self._awaitable().__await__()


class _cached_awaitable_task(object):
    slots = ['coro', 'task']

    def __init__(self, coro):
        self.coro = coro

    @cachedprop
    def task(self):
        return asyncio.create_task(self.coro)

    def __await__(self):
        return self.task.__await__()


class _cached_prop_loop(_cached_prop):
    def __get__(self, obj, cls):
        if obj is None:
            return self
        obj.__dict__[self.__name__] = rv = _cached_awaitable_coro(
            self.fget, obj)
        return rv


_pendulum_parsing_opts = {
    'day_first': False,
    'year_first': True,
    'strict': True,
    'exact': False,
    'now': None
}


def _pendulum_normalize(obj):
    if isinstance(obj, time):
        now = datetime.utcnow()
        obj = datetime(
            now.year, now.month, now.day,
            obj.hour, obj.minute, obj.second, obj.microsecond
        )
    elif isinstance(obj, date) and not isinstance(obj, datetime):
        obj = datetime(obj.year, obj.month, obj.day)
    return obj


def parse_datetime(text):
    parsed = _pendulum_normalize(
        _pendulum_parse(text, **_pendulum_parsing_opts))
    return pendulum.datetime(
        parsed.year, parsed.month, parsed.day,
        parsed.hour, parsed.minute, parsed.second, parsed.microsecond,
        tz=parsed.tzinfo or pendulum.UTC
    )


def is_valid_ip_address(address):
    REGEX_IPv4 = re.compile('(\d+)\.(\d+)\.(\d+)\.(\d+)')
    # deal with special cases
    if address.lower() in ('127.0.0.1', 'localhost', '::1',
                           '::ffff:127.0.0.1'):
        return True
    elif address.lower() in ('unknown', ''):
        return False
    elif address.count('.') == 3:  # assume IPv4
        if address.startswith('::ffff:'):
            address = address[7:]
        if hasattr(socket, 'inet_aton'):  # try validate using the OS
            try:
                socket.inet_aton(address)
                return True
            except socket.error:  # invalid address
                return False
        else:  # try validate using Regex
            match = REGEX_IPv4.match(address)
            if match and all(0 <= int(match.group(i)) < 256
                             for i in (1, 2, 3, 4)):
                return True
            return False
    elif hasattr(socket, 'inet_pton'):  # assume IPv6, try using the OS
        try:
            socket.inet_pton(socket.AF_INET6, address)
            return True
        except socket.error:  # invalid address
            return False
    else:  # do not know what to do? assume it is a valid address
        return True


def read_file(filename, mode='r'):
    # returns content from filename, making sure to close the file on exit.
    f = open(filename, mode)
    try:
        return f.read()
    finally:
        f.close()


def write_file(filename, value, mode='w'):
    # writes <value> to filename, making sure to close the file on exit.
    f = open(filename, mode)
    try:
        return f.write(value)
    finally:
        f.close()


def dict_to_sdict(obj):
    #: convert dict and nested dicts to sdict
    if isinstance(obj, dict) and not isinstance(obj, sdict):
        for k in obj:
            obj[k] = dict_to_sdict(obj[k])
        return sdict(obj)
    return obj
