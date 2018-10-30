# -*- coding: utf-8 -*-

from . import Protocol, protocols


@protocols.register('httptools', packages=['httptools'])
class HttpToolsProtocol(Protocol):
    def init(self):
        self.parser = self.httptools.HttpRequestParser(self)
