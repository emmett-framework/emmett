# -*- coding: utf-8 -*-
"""
    weppy.utils
    -----------

    Provides some utilities for weppy.

    :copyright: (c) 2014-2018 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

import pendulum
import re
import socket
from datetime import datetime, date, time
from pendulum.parsing import _parse as _pendulum_parse
from .datastructures import sdict


class cachedprop(object):
    #: a read-only @property that is only evaluated once.
    def __init__(self, fget, doc=None, name=None):
        self.fget = fget
        self.__doc__ = doc or fget.__doc__
        self.__name__ = name or fget.__name__

    def __get__(self, obj, cls):
        if obj is None:
            return self
        obj.__dict__[self.__name__] = result = self.fget(obj)
        return result


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
