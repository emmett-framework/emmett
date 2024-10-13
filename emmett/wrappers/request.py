# -*- coding: utf-8 -*-
"""
emmett.wrappers.request
-----------------------

Provides http request wrappers.

:copyright: 2014 Giovanni Barillari
:license: BSD-3-Clause
"""

import pendulum
from emmett_core.http.wrappers.request import Request as _Request
from emmett_core.utils import cachedprop


class Request(_Request):
    __slots__ = []

    method: str

    @cachedprop
    def now(self) -> pendulum.DateTime:
        return pendulum.instance(self._now)

    @cachedprop
    def now_local(self) -> pendulum.DateTime:
        return self.now.in_timezone(pendulum.local_timezone())  # type: ignore
