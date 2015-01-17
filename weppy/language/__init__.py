"""
    weppy.language
    --------------

    Provides the languages translator system.

    :copyright: (c) 2015 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""


class Instance(object):
    def T(self, *args, **kwargs):
        if not hasattr(self, "_t"):
            from ..expose import Expose
            from .translator import Translator
            self._t = Translator(Expose.application)
        return self._t(*args, **kwargs)

# We use a 'proxied' object to the translator to avoid errors
# when user calls T() outside the request flow.
_instance = Instance()
T = _instance.T
