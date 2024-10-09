# -*- coding: utf-8 -*-
"""
emmett.security
---------------

Miscellaneous security helpers.

:copyright: 2014 Giovanni Barillari
:license: BSD-3-Clause
"""

import hashlib
import hmac
import time
from collections import OrderedDict
from uuid import uuid4

from emmett_core.cryptography import kdf

# TODO: check bytes conversions
from ._shortcuts import to_bytes


class CSRFStorage(OrderedDict):
    def _clean(self):
        now = time.time()
        for key in list(self):
            if self[key] + 3600 > now:
                break
            del self[key]

    def gen_token(self):
        self._clean()
        token = str(uuid4())
        self[token] = int(time.time())
        return token


def md5_hash(text):
    """Generate a md5 hash with the given text"""
    return hashlib.md5(text).hexdigest()


def simple_hash(text, key="", salt="", digest_alg="md5"):
    """
    Generates hash with the given text using the specified
    digest hashing algorithm
    """
    if not digest_alg:
        raise RuntimeError("simple_hash with digest_alg=None")
    elif not isinstance(digest_alg, str):  # manual approach
        h = digest_alg(text + key + salt)
    elif digest_alg.startswith("pbkdf2"):  # latest and coolest!
        iterations, keylen, alg = digest_alg[7:-1].split(",")
        return kdf.pbkdf2_hex(
            text, salt, iterations=int(iterations), keylen=int(keylen), hash_algorithm=kdf.PBKDF2_HMAC[alg]
        )
    elif key:  # use hmac
        digest_alg = get_digest(digest_alg)
        h = hmac.new(to_bytes(key + salt), msg=to_bytes(text), digestmod=digest_alg)
    else:  # compatible with third party systems
        h = hashlib.new(digest_alg)
        h.update(to_bytes(text + salt))
    return h.hexdigest()


def get_digest(value):
    """
    Returns a hashlib digest algorithm from a string
    """
    if not isinstance(value, str):
        return value
    value = value.lower()
    if value == "md5":
        return hashlib.md5
    elif value == "sha1":
        return hashlib.sha1
    elif value == "sha224":
        return hashlib.sha224
    elif value == "sha256":
        return hashlib.sha256
    elif value == "sha384":
        return hashlib.sha384
    elif value == "sha512":
        return hashlib.sha512
    else:
        raise ValueError("Invalid digest algorithm: %s" % value)


DIGEST_ALG_BY_SIZE = {
    128 / 4: "md5",
    160 / 4: "sha1",
    224 / 4: "sha224",
    256 / 4: "sha256",
    384 / 4: "sha384",
    512 / 4: "sha512",
}
