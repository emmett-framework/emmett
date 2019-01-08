# -*- coding: utf-8 -*-
"""
    weppy._shortcuts
    ----------------

    Some shortcuts

    :copyright: (c) 2014-2019 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

import hashlib

hashlib_md5 = lambda s: hashlib.md5(bytes(s, 'utf8'))
hashlib_sha1 = lambda s: hashlib.sha1(bytes(s, 'utf8'))


def to_bytes(obj, charset='utf8', errors='strict'):
    if obj is None:
        return None
    if isinstance(obj, (bytes, bytearray, memoryview)):
        return bytes(obj)
    if isinstance(obj, str):
        return obj.encode(charset, errors)
    raise TypeError('Expected bytes')


def to_unicode(obj, charset='utf8', errors='strict'):
    if obj is None:
        return None
    if not isinstance(obj, bytes):
        return str(obj)
    return obj.decode(charset, errors)
