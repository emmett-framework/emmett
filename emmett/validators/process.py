# -*- coding: utf-8 -*-
"""
    emmett.validators.process
    -------------------------

    Validators that transform values.

    Ported from the original validators of web2py (http://www.web2py.com)

    :copyright: (c) by Massimo Di Pierro <mdipierro@cs.depaul.edu>
    :license: LGPLv3 (http://www.gnu.org/licenses/lgpl.html)
"""

import re
import unicodedata

# TODO: check unicode conversions
from .._shortcuts import to_unicode
from .basic import Validator
from .helpers import translate, LazyCrypt


class Cleanup(Validator):
    rule = re.compile(r"[^\x09\x0a\x0d\x20-\x7e]")

    def __init__(self, regex=None, message=None):
        super().__init__(message=message)
        self.regex = self.rule if regex is None else re.compile(regex)

    def __call__(self, value):
        v = self.regex.sub('', (to_unicode(value) or '').strip())
        return v, None


class Lower(Validator):
    def __call__(self, value):
        if value is None:
            return (value, None)
        return (to_unicode(value).lower(), None)


class Upper(Validator):
    def __call__(self, value):
        if value is None:
            return (value, None)
        return (to_unicode(value).upper(), None)


class Urlify(Validator):
    message = "Not convertible to url"

    def __init__(self, maxlen=80, check=False, keep_underscores=False, message=None):
        super().__init__(message=message)
        self.maxlen = maxlen
        self.check = check
        self.message = message
        self.keep_underscores = keep_underscores

    def __call__(self, value):
        if self.check and value != self._urlify(value):
            return value, translate(self.message)
        return self._urlify(value), None

    def _urlify(self, s):
        """
        Converts incoming string to a simplified ASCII subset.
        if (keep_underscores): underscores are retained in the string
        else: underscores are translated to hyphens (default)
        """
        s = to_unicode(s)
        # to lowercase
        s = s.lower()
        # replace special characters
        s = unicodedata.normalize("NFKD", s)
        # encode as ASCII
        s = s.encode("ascii", "ignore").decode("ascii")
        # strip html entities
        s = re.sub(r"&\w+?;", "", s)
        if self.keep_underscores:
            # whitespace to hypens
            s = re.sub(r"\s+", "-", s)
            # strip all but alphanumeric/underscore/hyphen
            s = re.sub(r"[^\w\-]", "", s)
        else:
            # whitespace & underscores to hyphens
            s = re.sub(r"[\s_]+", "-", s)
            # strip all but alphanumeric/hyphen
            s = re.sub(r"[^a-z0-9\-]", "", s)
        # collapse strings of hyphens
        s = re.sub(r"[-_][-_]+", "-", s)
        # remove leading and trailing hyphens
        s = s.strip(r"-")
        # enforce maximum length
        return s[:self.maxlen]


class Crypt(Validator):
    """
    encodes the value on validation with a digest.

    If no arguments are provided Crypt uses the MD5 algorithm.
    If the key argument is provided the HMAC+MD5 algorithm is used.
    If the digest_alg is specified this is used to replace the
    MD5 with, for example, SHA512. The digest_alg can be
    the name of a hashlib algorithm as a string or the algorithm itself.

    min_length is the minimal password length (default 4)
    error_message is the message if password is too short

    Notice that an empty password is accepted but invalid. It will not allow
    login back. Stores junk as hashed password.

    Specify an algorithm or by default we will use sha512.

    Typical available algorithms:
      md5, sha1, sha224, sha256, sha384, sha512

    If salt, it hashes a password with a salt.
    If salt is True, this method will automatically generate one.
    Either case it returns an encrypted password string with format:

      <algorithm>$<salt>$<hash>

    Important: hashed password is returned as a LazyCrypt object and computed
    only if needed. The LasyCrypt object also knows how to compare itself with
    an existing salted password
    """

    def __init__(
        self, key=None, algorithm='pbkdf2(1000,20,sha512)', salt=True, message=None
    ):
        super().__init__(message=message)
        self.key = key
        self.digest_alg = algorithm
        self.salt = salt

    def __call__(self, value):
        return LazyCrypt(self, value), None
