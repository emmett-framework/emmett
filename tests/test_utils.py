# -*- coding: utf-8 -*-
"""
tests.utils
-----------

Test Emmett utils engine
"""

from emmett.datastructures import sdict
from emmett.utils import dict_to_sdict, is_valid_ip_address


def test_is_valid_ip_address():
    result_localhost = is_valid_ip_address("127.0.0.1")
    assert result_localhost is True

    result_unknown = is_valid_ip_address("unknown")
    assert result_unknown is False

    result_ipv4_valid = is_valid_ip_address("::ffff:192.168.0.1")
    assert result_ipv4_valid is True

    result_ipv4_valid = is_valid_ip_address("192.168.256.1")
    assert result_ipv4_valid is False

    result_ipv6_valid = is_valid_ip_address("fd40:363d:ee85::")
    assert result_ipv6_valid is True

    result_ipv6_valid = is_valid_ip_address("fd40:363d:ee85::1::")
    assert result_ipv6_valid is False


def test_dict_to_sdict():
    result_sdict = dict_to_sdict({"test": "dict"})
    assert isinstance(result_sdict, sdict)
    assert result_sdict.test == "dict"

    result_number = dict_to_sdict(1)
    assert not isinstance(result_number, sdict)
    assert result_number == 1
