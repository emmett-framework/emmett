# deprecated since 1.0

from ._internal import warn_of_deprecation
from .html import tag, cat, safe, asis


warn_of_deprecation('weppy.tags', 'weppy.html', stack=3)
