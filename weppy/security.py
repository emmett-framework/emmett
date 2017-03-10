# -*- coding: utf-8 -*-
"""
    weppy.security
    --------------

    Miscellaneous security helping methods.

    :copyright: (c) 2014-2017 by Giovanni Barillari

    Based on the code of web2py (http://www.web2py.com)
    :copyright: (c) by Massimo Di Pierro <mdipierro@cs.depaul.edu>

    :license: LGPLv3 (http://www.gnu.org/licenses/lgpl.html)
"""

import base64
import hashlib
import hmac
import os
import pyaes
import random
import struct
import threading
import time
import uuid as uuidm
import zlib
from collections import OrderedDict

from ._compat import PY2, xrange, pickle, hashlib_sha1, to_bytes, to_native
from .libs.pbkdf2 import pbkdf2_hex


class CSRFStorage(OrderedDict):
    def _clean(self):
        now = time.time()
        for key in list(self):
            if self[key] + 3600 > now:
                break
            del self[key]

    def gen_token(self):
        self._clean()
        token = str(uuid())
        self[token] = int(time.time())
        return token


def md5_hash(text):
    """ Generate a md5 hash with the given text """
    return hashlib.md5(text).hexdigest()


def simple_hash(text, key='', salt='', digest_alg='md5'):
    """
    Generates hash with the given text using the specified
    digest hashing algorithm
    """
    if not digest_alg:
        raise RuntimeError("simple_hash with digest_alg=None")
    elif not isinstance(digest_alg, str):  # manual approach
        h = digest_alg(text + key + salt)
    elif digest_alg.startswith('pbkdf2'):  # latest and coolest!
        iterations, keylen, alg = digest_alg[7:-1].split(',')
        return pbkdf2_hex(to_bytes(text), to_bytes(salt), int(iterations),
                          int(keylen), get_digest(alg))
    elif key:  # use hmac
        digest_alg = get_digest(digest_alg)
        h = hmac.new(to_bytes(key + salt), to_bytes(text), digest_alg)
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
    128 / 4: 'md5',
    160 / 4: 'sha1',
    224 / 4: 'sha224',
    256 / 4: 'sha256',
    384 / 4: 'sha384',
    512 / 4: 'sha512',
}


def _pad(s, n=32, padchar='.'):
    expected_len = ((len(s) + n) - len(s) % n)
    return s.ljust(expected_len, to_bytes(padchar))
    #return s + (32 - len(s) % 32) * padchar


def secure_dumps(data, encryption_key, hash_key=None, compression_level=None):
    if not hash_key:
        hash_key = hashlib_sha1(encryption_key).hexdigest()
    dump = pickle.dumps(data)
    if compression_level:
        dump = zlib.compress(dump, compression_level)
    key = _pad(to_bytes(encryption_key[:32]))
    aes = pyaes.AESModeOfOperationCFB(key, iv=key[:16], segment_size=8)
    encrypted_data = base64.urlsafe_b64encode(aes.encrypt(_pad(dump)))
    signature = hmac.new(to_bytes(hash_key), encrypted_data).hexdigest()
    return signature + ':' + to_native(encrypted_data)


def secure_loads(data, encryption_key, hash_key=None, compression_level=None):
    if ':' not in data:
        return None
    if not hash_key:
        hash_key = hashlib_sha1(encryption_key).hexdigest()
    signature, encrypted_data = data.split(':', 1)
    actual_signature = hmac.new(
        to_bytes(hash_key), to_bytes(encrypted_data)).hexdigest()
    if signature != actual_signature:
        return None
    key = _pad(to_bytes(encryption_key[:32]))
    aes = pyaes.AESModeOfOperationCFB(key, iv=key[:16], segment_size=8)
    try:
        data = aes.decrypt(base64.urlsafe_b64decode(to_bytes(encrypted_data)))
        data = data.rstrip(to_bytes(' '))
        if compression_level:
            data = zlib.decompress(data)
        return pickle.loads(data)
    except (TypeError, pickle.UnpicklingError):
        return None


def _init_urandom():
    """
    This function and the web2py_uuid follow from the following discussion:
    http://groups.google.com/group/web2py-developers/browse_thread/thread/7fd5789a7da3f09

    At startup web2py compute a unique ID that identifies the machine by adding
    uuid.getnode() + int(time.time() * 1e3)

    This is a 48-bit number. It converts the number into 16 8-bit tokens.
    It uses this value to initialize the entropy source ('/dev/urandom')
    and to seed random.

    If os.random() is not supported, it falls back to using random and issues
    a warning.
    """
    node_id = uuidm.getnode()
    microseconds = int(time.time() * 1e6)
    ctokens = [((node_id + microseconds) >> ((i % 6) * 8)) %
               256 for i in xrange(16)]
    random.seed(node_id + microseconds)
    try:
        os.urandom(1)
        have_urandom = True
        try:
            # try to add process-specific entropy
            frandom = open('/dev/urandom', 'wb')
            try:
                if PY2:
                    frandom.write(''.join(chr(t) for t in ctokens))
                else:
                    frandom.write(bytes([]).join(bytes([t]) for t in ctokens))
            finally:
                frandom.close()
        except IOError:
            # works anyway
            pass
    except NotImplementedError:
        have_urandom = False
    if PY2:
        packed = ''.join(chr(x) for x in ctokens)
    else:
        packed = bytes([]).join(bytes([x]) for x in ctokens)
    unpacked_ctokens = struct.unpack('=QQ', packed)
    return unpacked_ctokens, have_urandom
_UNPACKED_CTOKENS, _HAVE_URANDOM = _init_urandom()


def fast_urandom16(urandom=[], locker=threading.RLock()):
    """
    this is 4x faster than calling os.urandom(16) and prevents
    the "too many files open" issue with concurrent access to os.urandom()
    """
    try:
        return urandom.pop()
    except IndexError:
        try:
            locker.acquire()
            ur = os.urandom(16 * 1024)
            urandom += [ur[i:i + 16] for i in xrange(16, 1024 * 16, 16)]
            return ur[0:16]
        finally:
            locker.release()


def uuid(ctokens=_UNPACKED_CTOKENS):
    """
    It works like uuid.uuid4 except that tries to use os.urandom() if possible
    and it XORs the output with the tokens uniquely associated with
    this machine.
    """
    rand_longs = (random.getrandbits(64), random.getrandbits(64))
    if _HAVE_URANDOM:
        urand_longs = struct.unpack('=QQ', fast_urandom16())
        byte_s = struct.pack('=QQ',
                             rand_longs[0] ^ urand_longs[0] ^ ctokens[0],
                             rand_longs[1] ^ urand_longs[1] ^ ctokens[1])
    else:
        byte_s = struct.pack('=QQ',
                             rand_longs[0] ^ ctokens[0],
                             rand_longs[1] ^ ctokens[1])
    return str(uuidm.UUID(bytes=byte_s, version=4))
