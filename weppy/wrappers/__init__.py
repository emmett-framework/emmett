# -*- coding: utf-8 -*-
"""
    weppy.wrappers
    --------------

    Provides request and response wrappers.

    :copyright: (c) 2014-2019 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""


class Wrapper(object):
    def __getitem__(self, key):
        return getattr(self, key, None)

    def __setitem__(self, key, value):
        setattr(self, key, value)
