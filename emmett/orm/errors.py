# -*- coding: utf-8 -*-
"""
    emmett.orm.errors
    -----------------

    Provides some error wrappers.

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""


class MaxConnectionsExceeded(RuntimeError):
    def __init__(self):
        super().__init__('Exceeded maximum connections')
