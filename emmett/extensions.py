# -*- coding: utf-8 -*-
"""
emmett.extensions
-----------------

Provides base classes to create extensions.

:copyright: 2014 Giovanni Barillari
:license: BSD-3-Clause
"""

from __future__ import annotations

from enum import Enum

from emmett_core.extensions import Extension as Extension, listen_signal as listen_signal


class Signals(str, Enum):
    __str__ = lambda v: v.value

    after_database = "after_database"
    after_loop = "after_loop"
    after_route = "after_route"
    before_database = "before_database"
    before_route = "before_route"
    before_routes = "before_routes"
