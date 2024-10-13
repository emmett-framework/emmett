# -*- coding: utf-8 -*-
"""
emmett.routing.urls
-------------------

Provides url builder apis.

:copyright: 2014 Giovanni Barillari
:license: BSD-3-Clause
"""

from emmett_core.routing.urls import Url

from ..ctx import current


url = Url(current)
