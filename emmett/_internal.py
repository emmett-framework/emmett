# -*- coding: utf-8 -*-
"""
emmett._internal
----------------

Provides internally used helpers and objects.

:copyright: 2014 Giovanni Barillari

Several parts of this code comes from Flask and Werkzeug.
:copyright: (c) 2014 by Armin Ronacher.

:license: BSD-3-Clause
"""

from __future__ import annotations

import datetime

import pendulum


#: monkey patches
def _pendulum_to_datetime(obj):
    return datetime.datetime(
        obj.year, obj.month, obj.day, obj.hour, obj.minute, obj.second, obj.microsecond, tzinfo=obj.tzinfo
    )


def _pendulum_to_naive_datetime(obj):
    obj = obj.in_timezone("UTC")
    return datetime.datetime(obj.year, obj.month, obj.day, obj.hour, obj.minute, obj.second, obj.microsecond)


def _pendulum_json(obj):
    return obj.for_json()


pendulum.DateTime.as_datetime = _pendulum_to_datetime  # type: ignore
pendulum.DateTime.as_naive_datetime = _pendulum_to_naive_datetime  # type: ignore
pendulum.DateTime.__json__ = _pendulum_json  # type: ignore
