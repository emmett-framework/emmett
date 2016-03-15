import re
from .._compat import to_unicode, to_native
from .basic import Validator
from .consist import isEmail
from .helpers import translate, options_sorter


# TODO port this
class isStrong(object):
    """
    enforces complexity requirements on a field
    """
    lowerset = frozenset(u'abcdefghijklmnopqrstuvwxyz')
    upperset = frozenset(u'ABCDEFGHIJKLMNOPQRSTUVWXYZ')
    numberset = frozenset(u'0123456789')
    sym1set = frozenset(u'!@#$%^&*()')
    sym2set = frozenset(u'~`-_=+[]{}\\|;:\'",.<>?/')
    otherset = frozenset(u'0123456789abcdefghijklmnopqrstuvwxyz')

    def __init__(self, min=None, max=None, upper=None, lower=None, number=None,
                 entropy=None,
                 special=None, specials=r'~!@#$%^&*()_+-=?<>,.:;{}[]|',
                 invalid=' "', error_message=None, es=False):
        self.entropy = entropy
        if entropy is None:
            # enforce default requirements
            self.min = 8 if min is None else min
            self.max = max  # was 20, but that doesn't make sense
            self.upper = 1 if upper is None else upper
            self.lower = 1 if lower is None else lower
            self.number = 1 if number is None else number
            self.special = 1 if special is None else special
        else:
            # by default, an entropy spec is exclusive
            self.min = min
            self.max = max
            self.upper = upper
            self.lower = lower
            self.number = number
            self.special = special
        self.specials = specials
        self.invalid = invalid
        self.error_message = error_message
        self.estring = es   # return error message as string (for doctest)

    def __call__(self, value):
        failures = []
        if value and len(value) == value.count('*') > 4:
            return (value, None)
        if self.entropy is not None:
            entropy = isStrong.calc_entropy(value)
            if entropy < self.entropy:
                failures.append(
                    translate(
                        "Entropy (%(have)s) less than required (%(need)s)")
                    % dict(have=entropy, need=self.entropy))
        if type(self.min) == int and self.min > 0:
            if not len(value) >= self.min:
                failures.append(translate("Minimum length is %s") % self.min)
        if type(self.max) == int and self.max > 0:
            if not len(value) <= self.max:
                failures.append(translate("Maximum length is %s") % self.max)
        if type(self.special) == int:
            all_special = [ch in value for ch in self.specials]
            if self.special > 0:
                if not all_special.count(True) >= self.special:
                    failures.append(
                        translate(
                            "Must include at least %s of the following: %s")
                        % (self.special, self.specials))
        if self.invalid:
            all_invalid = [ch in value for ch in self.invalid]
            if all_invalid.count(True) > 0:
                failures.append(
                    translate(
                        "May not contain any of the following: %s")
                    % self.invalid)
        if type(self.upper) == int:
            all_upper = re.findall("[A-Z]", value)
            if self.upper > 0:
                if not len(all_upper) >= self.upper:
                    failures.append(
                        translate("Must include at least %s upper case")
                        % str(self.upper))
            else:
                if len(all_upper) > 0:
                    failures.append(
                        translate("May not include any upper case letters"))
        if type(self.lower) == int:
            all_lower = re.findall("[a-z]", value)
            if self.lower > 0:
                if not len(all_lower) >= self.lower:
                    failures.append(
                        translate("Must include at least %s lower case")
                        % str(self.lower))
            else:
                if len(all_lower) > 0:
                    failures.append(
                        translate("May not include any lower case letters"))
        if type(self.number) == int:
            all_number = re.findall("[0-9]", value)
            if self.number > 0:
                numbers = "number"
                if self.number > 1:
                    numbers = "numbers"
                if not len(all_number) >= self.number:
                    failures.append(translate("Must include at least %s %s")
                                    % (str(self.number), numbers))
            else:
                if len(all_number) > 0:
                    failures.append(translate("May not include any numbers"))
        if len(failures) == 0:
            return (value, None)
        if not self.error_message:
            if self.estring:
                return (value, '|'.join(failures))
            from .templating import NOESCAPE
            return (value, NOESCAPE('<br />'.join(failures)))
        else:
            return (value, translate(self.error_message))

    @staticmethod
    def calc_entropy(string):
        " calculates a simple entropy for a given string "
        import math
        alphabet = 0    # alphabet size
        other = set()
        seen = set()
        lastset = None
        string = to_unicode(string)
        for c in string:
            # classify this character
            inset = isStrong.otherset
            for cset in (isStrong.lowerset, isStrong.upperset,
                         isStrong.numberset, isStrong.sym1set,
                         isStrong.sym2set):
                if c in cset:
                    inset = cset
                    break
            # calculate effect of character on alphabet size
            if inset not in seen:
                seen.add(inset)
                alphabet += len(inset)  # credit for a new character set
            elif c not in other:
                alphabet += 1   # credit for unique characters
                other.add(c)
            if inset is not lastset:
                alphabet += 1   # credit for set transitions
                lastset = cset
        entropy = len(
            string) * math.log(alphabet) / 0.6931471805599453  # math.log(2)
        return round(entropy, 2)


# TODO port this
class FilenameMatches(Validator):
    """
    Checks if name and extension of file uploaded through file input matches
    given criteria.

    Does *not* ensure the file type in any way. Returns validation failure
    if no data was uploaded.

    Args:
        filename: filename (before dot) regex
        extension: extension (after dot) regex
        lastdot: which dot should be used as a filename / extension separator:
            True means last dot, eg. file.png -> file / png
            False means first dot, eg. file.tar.gz -> file / tar.gz
        case:
            0 - keep the case,
            1 - transform the string into lowercase (default),
            2 - transform the string into uppercase

    If there is no dot present, extension checks will be done against empty
    string and filename checks against whole value.
    """

    def __init__(self, filename=None, extension=None, lastdot=True, case=1,
                 error_message='Enter valid filename'):
        if isinstance(filename, str):
            filename = re.compile(filename)
        if isinstance(extension, str):
            extension = re.compile(extension)
        self.filename = filename
        self.extension = extension
        self.lastdot = lastdot
        self.case = case
        self.error_message = error_message

    def __call__(self, value):
        try:
            string = value.filename
        except:
            return (value, translate(self.error_message))
        if self.case == 1:
            string = string.lower()
        elif self.case == 2:
            string = string.upper()
        if self.lastdot:
            dot = string.rfind('.')
        else:
            dot = string.find('.')
        if dot == -1:
            dot = len(string)
        if self.filename and not self.filename.match(string[:dot]):
            return (value, translate(self.error_message))
        elif self.extension and not self.extension.match(string[dot + 1:]):
            return (value, translate(self.error_message))
        else:
            return (value, None)


# Kept for reference (v0.3 and below)
class isEmailList(object):
    split_emails = re.compile('[^,;\s]+')

    def __init__(self, error_message='Invalid emails: %s'):
        self.error_message = error_message

    def __call__(self, value):
        bad_emails = []
        emails = []
        f = isEmail()
        for email in self.split_emails.findall(value):
            if email not in emails:
                emails.append(email)
            error = f(email)[1]
            if error and email not in bad_emails:
                bad_emails.append(email)
        if not bad_emails:
            return (value, None)
        else:
            return (value,
                    translate(self.error_message) % ', '.join(bad_emails))

    def formatter(self, value, row=None):
        return ', '.join(value or [])


# Kept for reference (v0.3 and below)
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


# Kept for reference (v0.3 and below)
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
        value = to_native(to_unicode(value))
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
