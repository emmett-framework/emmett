# deprecated since 1.0

from ._internal import warn_of_deprecation
from .orm.base import Database
from .orm.objects import Field
from .orm.models import Model
from .orm.apis import belongs_to, refers_to, has_one, has_many, compute, \
    rowattr, rowmethod, before_insert, before_update, before_delete, \
    after_insert, after_update, after_delete, scope


warn_of_deprecation('weppy.dal', 'weppy.orm', stack=3)


class DAL(Database):
    def __init__(self, *args, **kwargs):
        warn_of_deprecation('weppy.dal.DAL', 'weppy.orm.Database', stack=4)
        return super(DAL, self).__init__(*args, **kwargs)
