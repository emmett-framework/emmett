# -*- coding: utf-8 -*-
"""
emmett.utils
------------

Provides some utilities for Emmett.

:copyright: 2014 Giovanni Barillari
:license: BSD-3-Clause
"""

from __future__ import annotations

import re
import socket
from datetime import date, datetime, time

import pendulum
from emmett_core.utils import cachedprop as cachedprop
from pendulum.parsing import _parse as _pendulum_parse

from .datastructures import sdict


_pendulum_parsing_opts = {"day_first": False, "year_first": True, "strict": True, "exact": False, "now": None}


def _pendulum_normalize(obj):
    if isinstance(obj, time):
        now = datetime.utcnow()
        obj = datetime(now.year, now.month, now.day, obj.hour, obj.minute, obj.second, obj.microsecond)
    elif isinstance(obj, date) and not isinstance(obj, datetime):
        obj = datetime(obj.year, obj.month, obj.day)
    return obj


def parse_datetime(text):
    parsed = _pendulum_normalize(_pendulum_parse(text, **_pendulum_parsing_opts))
    return pendulum.datetime(
        parsed.year,
        parsed.month,
        parsed.day,
        parsed.hour,
        parsed.minute,
        parsed.second,
        parsed.microsecond,
        tz=parsed.tzinfo or pendulum.UTC,
    )


_re_ipv4 = re.compile(r"(\d+)\.(\d+)\.(\d+)\.(\d+)")


def is_valid_ip_address(address):
    # deal with special cases
    if address.lower() in ["127.0.0.1", "localhost", "::1", "::ffff:127.0.0.1"]:
        return True
    elif address.lower() in ("unknown", ""):
        return False
    elif address.count(".") == 3:  # assume IPv4
        if address.startswith("::ffff:"):
            address = address[7:]
        if hasattr(socket, "inet_aton"):  # try validate using the OS
            try:
                socket.inet_aton(address)
                return True
            except socket.error:  # invalid address
                return False
        else:  # try validate using Regex
            match = _re_ipv4.match(address)
            if match and all(0 <= int(match.group(i)) < 256 for i in (1, 2, 3, 4)):
                return True
            return False
    elif hasattr(socket, "inet_pton"):  # assume IPv6, try using the OS
        try:
            socket.inet_pton(socket.AF_INET6, address)
            return True
        except socket.error:  # invalid address
            return False
    else:  # do not know what to do? assume it is a valid address
        return True


def read_file(filename, mode="r"):
    # returns content from filename, making sure to close the file on exit.
    f = open(filename, mode)
    try:
        return f.read()
    finally:
        f.close()


def write_file(filename, value, mode="w"):
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
