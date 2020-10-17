# -*- coding: utf-8 -*-
"""
    emmett.validators.inside
    ------------------------

    Validators that check presence/absence of given value in a set.

    :copyright: 2014 Giovanni Barillari

    Based on the web2py's validators (http://www.web2py.com)
    :copyright: (c) by Massimo Di Pierro <mdipierro@cs.depaul.edu>

    :license: LGPLv3 (http://www.gnu.org/licenses/lgpl.html)
"""

# TODO: check unicode conversions
from .._shortcuts import to_unicode
from ..ctx import current
from ..utils import cachedprop
from .basic import Validator
from .helpers import options_sorter, translate


class inRange(Validator):
    def __init__(self, minimum=None, maximum=None, include=(True, False), message=None):
        super().__init__(message=message)
        self.minimum = minimum
        self.maximum = maximum
        self.inc = include

    def _gt(self, val1, val2, eq=False):
        if eq:
            return val1 >= val2
        return val1 > val2

    def _lt(self, val1, val2, eq=False):
        if eq:
            return val1 <= val2
        return val1 < val2

    def __call__(self, value):
        minimum = self.minimum() if callable(self.minimum) else self.minimum
        maximum = self.maximum() if callable(self.maximum) else self.maximum
        if (
            (minimum is None or self._gt(value, minimum, self.inc[0])) and
            (maximum is None or self._lt(value, maximum, self.inc[1]))
        ):
            return value, None
        return value, translate(
            self._range_error(self.message, minimum, maximum)
        )

    def _range_error(self, message, minimum, maximum):
        if message is None:
            message = "Enter a value"
            if minimum is not None and maximum is not None:
                message += " between {min} and {max}"
            elif minimum is not None:
                message += " greater than or equal to {min}"
            elif maximum is not None:
                message += " less than or equal to {max}"
        if isinstance(maximum, int):
            maximum -= 1
        return translate(message).format(min=minimum, max=maximum)


class inSet(Validator):
    def __init__(
        self,
        theset,
        labels=None,
        multiple=False,
        zero=None,
        sort=False,
        message=None
    ):
        super().__init__(message=message)
        self.multiple = multiple
        if (
            theset and
            isinstance(theset, (tuple, list)) and
            isinstance(theset[0], (tuple, list)) and
            len(theset[0]) == 2
        ):
            self.theset = [str(item) for item, label in theset]
            self.labels = [str(label) for item, label in theset]
        else:
            self.theset = [str(item) for item in theset]
            self.labels = labels
        self.zero = zero
        self.sort = sort

    def options(self, zero=True):
        if not self.labels:
            items = [(k, k) for (i, k) in enumerate(self.theset)]
        else:
            items = [(k, self.labels[i]) for (i, k) in enumerate(self.theset)]
        if self.sort:
            items.sort(options_sorter)
        if zero and self.zero is not None and not self.multiple:
            items.insert(0, ('', self.zero))
        return items

    def __call__(self, value):
        if self.multiple:
            if not value:
                values = []
            elif isinstance(value, (tuple, list)):
                values = value
            else:
                values = [value]
        else:
            values = [value]
        failures = [
            x for x in values
            if (to_unicode(x) or '') not in self.theset]
        if failures and self.theset:
            if self.multiple and (value is None or value == ''):
                return ([], None)
            return value, translate(self.message)
        if self.multiple:
            if (
                isinstance(self.multiple, (tuple, list)) and
                not self.multiple[0] <= len(values) < self.multiple[1]
            ):
                return values, translate(self.message)
            return values, None
        return value, None


class DBValidator(Validator):
    def __init__(self, db, tablename, fieldname='id', dbset=None, message=None):
        super().__init__(message=message)
        self.db = db
        self.tablename = tablename
        self.fieldname = fieldname
        self._dbset = dbset

    def __call__(self, value):
        raise NotImplementedError

    @cachedprop
    def table(self):
        return self.db[self.tablename]

    @cachedprop
    def dbset(self):
        if self._dbset:
            return self._dbset(self.db)
        return self.db(self.table)

    @cachedprop
    def field(self):
        return self.table[self.fieldname]


class inDB(DBValidator):
    def __init__(
        self,
        db,
        tablename,
        fieldname='id',
        dbset=None,
        label_field=None,
        multiple=False,
        orderby=None,
        message=None
    ):
        super().__init__(
            db,
            tablename,
            fieldname=fieldname,
            dbset=dbset,
            message=message
        )
        self.label_field = label_field
        self.multiple = multiple
        self.orderby = orderby

    @cachedprop
    def sorting(self):
        if callable(self.orderby):
            return self.orderby(self.table)
        return None

    def _get_rows(self):
        return self.dbset.select(orderby=self.sorting)

    def options(self, zero=True):
        records = self._get_rows()
        if self.label_field:
            items = [(r.id, str(r[self.label_field])) for r in records]
        elif self.db[self.tablename]._format:
            items = [(r.id, self.db[self.tablename]._format % r) for r in records]
        else:
            items = [(r.id, r.id) for r in records]
        #if self.sort:
        #    items.sort(options_sorter)
        #if zero and self.zero is not None and not self.multiple:
        #    items.insert(0, ('', self.zero))
        return items

    def __call__(self, value):
        if self.multiple:
            values = value if isinstance(value, list) else [value]
            records = self.dbset.where(
                self.field.belongs(values)
            ).select(self.field, distinct=True).column(self.field)
            if set(values).issubset(set(records)):
                return values, None
        else:
            if self.dbset.where(self.field == value).count():
                return value, None
        return value, translate(self.message)


class notInDB(DBValidator):
    def __call__(self, value):
        row = self.dbset.where(
            self.field == value
        ).select(limitby=(0, 1)).first()
        if row:
            record_id = getattr(current, '_dbvalidation_record_id_', None)
            if row.id != record_id:
                return value, translate(self.message)
        return value, None
