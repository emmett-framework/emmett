"""
    weppy.language
    --------------

    Provides the languages translator system.

    :copyright: (c) 2014-2017 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

from ..utils import cachedprop


class Instance(object):
    @cachedprop
    def _t(self):
        from ..expose import Expose
        from .translator import Translator
        return Translator(Expose.application)

    def T(self, *args, **kwargs):
        return self._t(*args, **kwargs)


# We use a 'proxied' object to the translator to avoid errors
# when user calls T() outside the request flow.
_instance = Instance()
T = _instance.T
