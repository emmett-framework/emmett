# -*- coding: utf-8 -*-
"""
emmett.tools.stream
-------------------

Provides the stream handlers.

:copyright: 2014 Giovanni Barillari
:license: BSD-3-Clause
"""

from emmett_core.pipeline.extras import SSEPipe as _SSEPipe, StreamPipe as _StreamPipe

from ..ctx import current


class StreamPipe(_StreamPipe):
    _current = current


class SSEPipe(_SSEPipe):
    _current = current
