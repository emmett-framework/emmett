from ...helpers import Registry

protocols = Registry()

from . import h11

try:
    from . import httptools
except ImportError:
    pass

from . import auto
