# -*- coding: utf-8 -*-

from .. import ProtocolWrapperRegistry, ProtocolWrapper


protocols = ProtocolWrapperRegistry()

from . import (
    auto,
    h11,
    httptools
)
