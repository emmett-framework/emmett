# TODO: refactor following validators

import re
from .basic import Validator
from .consist import isEmail
from .helpers import translate


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


class isStrong(object):
    """
    enforces complexity requirements on a field
    """
    lowerset = frozenset(unicode('abcdefghijklmnopqrstuvwxyz'))
    upperset = frozenset(unicode('ABCDEFGHIJKLMNOPQRSTUVWXYZ'))
    numberset = frozenset(unicode('0123456789'))
    sym1set = frozenset(unicode('!@#$%^&*()'))
    sym2set = frozenset(unicode('~`-_=+[]{}\\|;:\'",.<>?/'))
    otherset = frozenset(unicode('0123456789abcdefghijklmnopqrstuvwxyz'))

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
        if isinstance(string, str):
            string = unicode(string, encoding='utf8')
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
