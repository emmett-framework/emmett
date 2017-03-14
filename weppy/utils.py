# -*- coding: utf-8 -*-
"""
    weppy.utils
    -----------

    Provides some utilities for weppy.

    :copyright: (c) 2014-2017 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

import re
import socket
from datetime import datetime
from pendulum.parser import Parser as PendulumParser
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


class DTParser(PendulumParser):
    def parse(self, text):
        try:
            parsed = self.normalize(self.parse_common(text))
            return self._create_pendulum_object(parsed)
        except:
            raise ValueError('Invalid date string: {}'.format(text))


dt_parser = DTParser(now=datetime.utcnow())


def parse_datetime(text):
    return dt_parser.parse(text)


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
