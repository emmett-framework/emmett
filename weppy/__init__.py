__version__ = '1.0.7'

from .app import App, AppModule
from .cache import Cache
from .datastructures import sdict
from .expose import url
from .forms import Form
from .globals import request, response, session, now
from .handlers import Handler, Helper
from .helpers import abort, stream_file
from .html import asis
from .http import redirect
from .language import T
from .orm import Field
from .pipeline import Pipe, Injector


# deprecated since 1.0
from .orm import Database as _DAL


class DAL(_DAL):
    def __init__(self, *args, **kwargs):
        from ._internal import warn_of_deprecation
        warn_of_deprecation('weppy.DAL', 'weppy.orm.Database', stack=4)
        return super(DAL, self).__init__(*args, **kwargs)
