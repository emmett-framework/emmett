from ...helpers import Registry

protocols = Registry()

from . import websockets

try:
    from . import wsproto
except ImportError:
    pass

from . import auto
