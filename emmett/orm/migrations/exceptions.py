# -*- coding: utf-8 -*-
"""
    emmett.orm.migrations.exceptions
    --------------------------------

    Provides exceptions for migration operations.

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""


class RevisionError(Exception):
    pass


class RangeNotAncestorError(RevisionError):
    def __init__(self, lower, upper):
        self.lower = lower
        self.upper = upper
        super(RangeNotAncestorError, self).__init__(
            "Revision %s is not an ancestor of revision %s" %
            (lower or "base", upper or "base")
        )


class MultipleHeads(RevisionError):
    def __init__(self, heads, argument):
        self.heads = heads
        self.argument = argument
        super(MultipleHeads, self).__init__(
            "Multiple heads are present for given argument '%s'; "
            "%s" % (argument, ", ".join(heads))
        )


class ResolutionError(RevisionError):
    def __init__(self, message, argument):
        super(ResolutionError, self).__init__(message)
        self.argument = argument
