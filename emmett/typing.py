# -*- coding: utf-8 -*-
"""
    emmett.typing
    -------------

    Provides typing helpers.

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

from typing import Awaitable, Callable, TypeVar

T = TypeVar("T")
KT = TypeVar("KT")
VT = TypeVar("VT")

ErrorHandlerType = TypeVar("ErrorHandlerType", bound=Callable[[], Awaitable[str]])
