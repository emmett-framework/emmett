# -*- coding: utf-8 -*-

import sys


class BuilderRegistry(object):
    def __init__(self):
        self.registry = {}
        self.builders = {}

    def register(self, name, packages=[]):
        def wrap(builder):
            self.registry[name] = builder
            loaded_packages, implemented = {}, True
            try:
                for package in packages:
                    __import__(package)
                    loaded_packages[package] = sys.modules[package]
            except ImportError:
                implemented = False
            if implemented:
                self.builders[name] = (builder, loaded_packages)
            return builder
        return wrap
