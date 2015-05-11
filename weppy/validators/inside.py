# -*- coding: utf-8 -*-
"""
    weppy.validators.inside
    -----------------------

    Validators that check presence/absence of given value in a set.

    Ported from the original validators of web2py (http://www.web2py.com)

    :copyright: (c) by Massimo Di Pierro <mdipierro@cs.depaul.edu>
    :license: LGPLv3 (http://www.gnu.org/licenses/lgpl.html)
"""


import re
from .basic import Validator
from .helpers import options_sorter, translate


class inRange(Validator):
    def __init__(self, minimum=None, maximum=None, message=None):
        self.minimum = minimum
        self.maximum = maximum
        self.message = message

    def __call__(self, value):
        minimum = self.minimum() if callable(self.minimum) else self.minimum
        maximum = self.maximum() if callable(self.maximum) else self.maximum
        if (minimum is None or value >= minimum) and \
                (maximum is None or value < maximum):
            return value, None
        return value, translate(
            self._range_error(self.message, minimum, maximum)
        )

    def _range_error(self, error_message, minimum, maximum):
        if error_message is None:
            error_message = 'Enter a value'
            if minimum is not None and maximum is not None:
                error_message += ' between %(min)g and %(max)g'
            elif minimum is not None:
                error_message += ' greater than or equal to %(min)g'
            elif maximum is not None:
                error_message += ' less than or equal to %(max)g'
        if type(maximum) in [int, long]:
            maximum -= 1
        return translate(error_message) % dict(min=minimum, max=maximum)


class inSet(Validator):
    """
    Check that value is one of the given list or set.
    """

    def __init__(self, theset, labels=None, message='Value not allowed',
                 multiple=False, zero=None, sort=False):
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
        self.error_message = message
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
        thestrset = [str(x) for x in self.theset]
        failures = [x for x in values if not str(x) in thestrset]
        if failures and self.theset:
            if self.multiple and (value is None or value == ''):
                return ([], None)
            return value, translate(self.error_message)
        if self.multiple:
            if isinstance(self.multiple, (tuple, list)) and \
                    not self.multiple[0] <= len(values) < self.multiple[1]:
                return values, translate(self.error_message)
            return values, None
        return value, None


class inSubSet(inSet):
    REGEX_W = re.compile('\w+')

    def __init__(self, *a, **b):
        inSet.__init__(self, *a, **b)

    def __call__(self, value):
        values = self.REGEX_W.findall(str(value))
        failures = [x for x in values if inSet.__call__(self, x)[1]]
        if failures:
            return value, translate(self.error_message)
        return value, None


class inDB(Validator):
    def __init__(self, db, set, field='_id', message=None):
        self.db = db
        self.set = set
        self.field = field
        # TODO: parse set if is not table

    def __call__(self, value):
        field = self.db[self.set][self.field]
        if self.db(field == value).count():
            return value, None
        return value, translate(self.message)


class notInDB(inDB):
    def __call__(self, value):
        field = self.db[self.set][self.field]
        if self.db(field == value).count():
            return value, translate(self.message)
        return value, None


class inDb(Validator):
    """
    Used for reference fields, rendered as a dropbox
    """
    regex1 = re.compile('\w+\.\w+')
    regex2 = re.compile('%\(([^\)]+)\)\d*(?:\.\d+)?[a-zA-Z]')

    def __init__(
        self,
        dbset,
        field,
        label=None,
        error_message='Value not in database',
        orderby=None,
        groupby=None,
        distinct=None,
        cache=None,
        multiple=False,
        zero='',
        sort=False,
        _and=None,
    ):
        from pydal.objects import Table
        if isinstance(field, Table):
            field = field._id

        if hasattr(dbset, 'define_table'):
            self.dbset = dbset()
        else:
            self.dbset = dbset
        (ktable, kfield) = str(field).split('.')
        if not label:
            label = '%%(%s)s' % kfield
        if isinstance(label, str):
            if self.regex1.match(str(label)):
                label = '%%(%s)s' % str(label).split('.')[-1]
            ks = self.regex2.findall(label)
            if kfield not in ks:
                ks += [kfield]
            fields = ks
        else:
            ks = [kfield]
            fields = 'all'
        self.fields = fields
        self.label = label
        self.ktable = ktable
        self.kfield = kfield
        self.ks = ks
        self.error_message = error_message
        self.theset = None
        self.orderby = orderby
        self.groupby = groupby
        self.distinct = distinct
        self.cache = cache
        self.multiple = multiple
        self.zero = zero
        self.sort = sort
        self._and = _and

    def set_self_id(self, id):
        if self._and:
            self._and.record_id = id

    def build_set(self):
        from pydal.objects import FieldVirtual, FieldMethod
        table = self.dbset.db[self.ktable]
        if self.fields == 'all':
            fields = [f for f in table]
        else:
            fields = [table[k] for k in self.fields]
        ignore = (FieldVirtual, FieldMethod)
        fields = filter(lambda f: not isinstance(f, ignore), fields)
        if self.dbset.db._dbname != 'gae':
            orderby = self.orderby or reduce(lambda a, b: a | b, fields)
            groupby = self.groupby
            distinct = self.distinct
            dd = dict(orderby=orderby, groupby=groupby,
                      distinct=distinct, cache=self.cache,
                      cacheable=True)
            records = self.dbset(table).select(*fields, **dd)
        else:
            orderby = self.orderby or \
                reduce(lambda a, b: a | b, (
                    f for f in fields if not f.name == 'id'))
            dd = dict(orderby=orderby, cache=self.cache, cacheable=True)
            records = self.dbset(table).select(table.ALL, **dd)
        self.theset = [str(r[self.kfield]) for r in records]
        if isinstance(self.label, str):
            self.labels = [self.label % r for r in records]
        else:
            self.labels = [self.label(r) for r in records]

    def options(self, zero=True):
        self.build_set()
        items = [(k, self.labels[i]) for (i, k) in enumerate(self.theset)]
        if self.sort:
            items.sort(options_sorter)
        if zero and self.zero is not None and not self.multiple:
            items.insert(0, ('', self.zero))
        return items

    def __call__(self, value):
        table = self.dbset.db[self.ktable]
        field = table[self.kfield]
        if self.multiple:
            if self._and:
                raise NotImplementedError
            if isinstance(value, list):
                values = value
            elif value:
                values = [value]
            else:
                values = []
            if isinstance(self.multiple, (tuple, list)) and \
                    not self.multiple[0] <= len(values) < self.multiple[1]:
                return values, translate(self.error_message)
            if self.theset:
                if not [v for v in values if v not in self.theset]:
                    return values, None
            else:
                from pydal.adapters import GoogleDatastoreAdapter

                def count(values, s=self.dbset, f=field):
                    return s(f.belongs(map(int, values))).count()
                if isinstance(self.dbset.db._adapter, GoogleDatastoreAdapter):
                    range_ids = range(0, len(values), 30)
                    total = sum(count(values[i:i + 30]) for i in range_ids)
                    if total == len(values):
                        return values, None
                elif count(values) == len(values):
                    return values, None
        elif self.theset:
            if str(value) in self.theset:
                if self._and:
                    return self._and(value)
                else:
                    return value, None
        else:
            if self.dbset(field == value).count():
                if self._and:
                    return self._and(value)
                else:
                    return value, None
        return value, translate(self.error_message)


class notInDb(Validator):
    """
    makes the field unique
    """

    def __init__(
        self,
        dbset,
        field,
        error_message='Value already in database or empty',
        allowed_override=[],
        ignore_common_filters=False,
    ):

        from pydal.objects import Table
        if isinstance(field, Table):
            field = field._id

        if hasattr(dbset, 'define_table'):
            self.dbset = dbset()
        else:
            self.dbset = dbset
        self.field = field
        self.error_message = error_message
        self.record_id = 0
        self.allowed_override = allowed_override
        self.ignore_common_filters = ignore_common_filters

    def set_self_id(self, id):
        self.record_id = id

    def __call__(self, value):
        if isinstance(value, unicode):
            value = value.encode('utf8')
        else:
            value = str(value)
        if not value.strip():
            return value, translate(self.error_message)
        if value in self.allowed_override:
            return value, None
        (tablename, fieldname) = str(self.field).split('.')
        table = self.dbset.db[tablename]
        field = table[fieldname]
        subset = self.dbset(field == value,
                            ignore_common_filters=self.ignore_common_filters)
        id = self.record_id
        if isinstance(id, dict):
            fields = [table[f] for f in id]
            row = subset.select(*fields, **dict(
                limitby=(0, 1), orderby_on_limitby=False)).first()
            if row and any(str(row[f]) != str(id[f]) for f in id):
                return value, translate(self.error_message)
        else:
            row = subset.select(table._id, field, limitby=(0, 1),
                                orderby_on_limitby=False).first()
            if row and str(row.id) != str(id):
                return value, translate(self.error_message)
        return value, None
