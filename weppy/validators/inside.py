# -*- coding: utf-8 -*-
"""
    weppy.validators.inside
    -----------------------

    Validators that check presence/absence of given value in a set.

    :copyright: (c) 2015 by Giovanni Barillari

    Based on the web2py's validators (http://www.web2py.com)
    :copyright: (c) by Massimo Di Pierro <mdipierro@cs.depaul.edu>

    :license: LGPLv3 (http://www.gnu.org/licenses/lgpl.html)
"""

from .._compat import integer_types
from .basic import Validator
from .helpers import options_sorter, translate


class inRange(Validator):
    def __init__(self, minimum=None, maximum=None, include=(True, False),
                 message=None):
        Validator.__init__(self, message)
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
        if ((minimum is None or self._gt(value, minimum, self.inc[0])) and
                (maximum is None or self._lt(value, maximum, self.inc[1]))):
            return value, None
        return value, translate(
            self._range_error(self.message, minimum, maximum)
        )

    def _range_error(self, message, minimum, maximum):
        if message is None:
            message = 'Enter a value'
            if minimum is not None and maximum is not None:
                message += ' between %(min)s and %(max)s'
            elif minimum is not None:
                message += ' greater than or equal to %(min)s'
            elif maximum is not None:
                message += ' less than or equal to %(max)s'
        if isinstance(maximum, integer_types):
            maximum -= 1
        return translate(message) % dict(min=minimum, max=maximum)


class inSet(Validator):
    """
    Check that value is one of the given list or set.
    """

    def __init__(self, theset, labels=None, multiple=False, zero=None,
                 sort=False, message=None):
        Validator.__init__(self, message)
        self.multiple = multiple
        #if isinstance(theset, dict):
        #    self.theset = [str(item) for item in theset]
        #    self.labels = theset.values()
        if theset and isinstance(theset, (tuple, list)) \
                and isinstance(theset[0], (tuple, list)) \
                and len(theset[0]) == 2:
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
        failures = [x for x in values if str(x) not in self.theset]
        if failures and self.theset:
            if self.multiple and (value is None or value == ''):
                return ([], None)
            return value, translate(self.message)
        if self.multiple:
            if isinstance(self.multiple, (tuple, list)) and \
                    not self.multiple[0] <= len(values) < self.multiple[1]:
                return values, translate(self.message)
            return values, None
        return value, None


#class inSubSet(inSet):
#    REGEX_W = re.compile('\w+')
#
#    def __init__(self, *a, **b):
#        inSet.__init__(self, *a, **b)
#
#    def __call__(self, value):
#        values = self.REGEX_W.findall(str(value))
#        failures = [x for x in values if inSet.__call__(self, x)[1]]
#        if failures:
#            return value, translate(self.error_message)
#        return value, None


class inDB(Validator):
    def __init__(self, db, set, field='id', label_field=None, multiple=False,
                 message=None):
        Validator.__init__(self, message)
        self.db = db
        self.set = set
        self.field = field
        self.label_field = label_field
        self.multiple = multiple
        # TODO: parse set if is not table

    def _get_set(self):
        self.db._adapter.reconnect()
        rv = self.db(self.db[self.set].id > 0).select().as_list()
        self.db._adapter.close()
        return rv

    def options(self, zero=True):
        records = self._get_set()
        if self.label_field:
            items = [(r['id'], str(r[self.label_field]))
                     for (i, r) in enumerate(records)]
        else:
            items = [(r['id'], self.db[self.set]._format % r)
                     for (i, r) in enumerate(records)]
        #if self.sort:
        #    items.sort(options_sorter)
        #if zero and self.zero is not None and not self.multiple:
        #    items.insert(0, ('', self.zero))
        return items

    def __call__(self, value):
        field = self.db[self.set][self.field]
        if self.multiple:
            if isinstance(value, list):
                values = value
            else:
                values = [value]
            records = [i[0] for i in self._get_set()]
            if not [v for v in values if v not in records]:
                return values, None
        else:
            if self.db(field == value).count():
                return value, None
        return value, translate(self.message)


class notInDB(Validator):
    def __init__(self, db, set, field='id', message=None):
        Validator.__init__(self, message)
        self.db = db
        self.set = set
        self.field = field
        self.record_id = None

    def __call__(self, value):
        field = self.db[self.set][self.field]
        row = self.db(field == value).select().first()
        if row:
            from ..globals import current
            record_id = getattr(current, '_form_validation_record_id_', None)
            if row.id != record_id:
                return value, translate(self.message)
        return value, None
