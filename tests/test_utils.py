# -*- coding: utf-8 -*-
"""
    tests.utils
    -----------

    Test Emmett utils engine
"""

import pytest

from emmett.datastructures import sdict
from emmett.utils import (
    cachedprop, _cached_prop_sync, _cached_prop_loop,
    dict_to_sdict, is_valid_ip_address)


class Class:
    def __init__(self):
        self.calls = 0

    @cachedprop
    def prop(self):
        self.calls += 1
        return 'test_cachedprop_sync'

    @cachedprop
    async def prop_loop(self):
        self.calls += 1
        return 'test_cachedprop_loop'


def test_cachedprop_sync():
    assert isinstance(Class.prop, _cached_prop_sync)
    obj = Class()
    assert obj.calls == 0
    assert obj.prop == 'test_cachedprop_sync'
    assert obj.calls == 1
    assert obj.prop == 'test_cachedprop_sync'
    assert obj.calls == 1


@pytest.mark.asyncio
async def test_cachedprop_loop():
    assert isinstance(Class.prop_loop, _cached_prop_loop)
    obj = Class()
    assert obj.calls == 0
    assert (await obj.prop_loop) == 'test_cachedprop_loop'
    assert obj.calls == 1
    assert (await obj.prop_loop) == 'test_cachedprop_loop'
    assert obj.calls == 1


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
