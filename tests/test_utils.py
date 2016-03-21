# -*- coding: utf-8 -*-
"""
    tests.utils
    ----------------

    Test weppy utils engine

    :copyright: (c) 2014-2016 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

from weppy.datastructures import sdict
from weppy.utils import cachedprop, dict_to_sdict, is_valid_ip_address


class TestClass(object):

    @cachedprop
    def prop(self):
        return 'test_cachedprop'


def test_cachedprop():
    assert isinstance(TestClass.prop, cachedprop)
    obj = TestClass()
    assert obj.prop == 'test_cachedprop'


def test_is_valid_ip_address():
    result_localhost = is_valid_ip_address('127.0.0.1')
    assert result_localhost is True

    result_unknown = is_valid_ip_address('unknown')
    assert result_unknown is False

    result_ipv4_valid = is_valid_ip_address('::ffff:192.168.0.1')
    assert result_ipv4_valid is True

    result_ipv4_valid = is_valid_ip_address('192.168.256.1')
    assert result_ipv4_valid is False

    result_ipv6_valid = is_valid_ip_address('fd40:363d:ee85::')
    assert result_ipv6_valid is True

    result_ipv6_valid = is_valid_ip_address('fd40:363d:ee85::1::')
    assert result_ipv6_valid is False


def test_dict_to_sdict():
    result_sdict = dict_to_sdict({'test': 'dict'})
    assert isinstance(result_sdict, sdict)
    assert result_sdict.test == 'dict'

    result_number = dict_to_sdict(1)
    assert not isinstance(result_number, sdict)
    assert result_number == 1
