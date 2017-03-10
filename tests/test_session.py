# -*- coding: utf-8 -*-
"""
    tests.session
    ----------------

    Test weppy session module

    :copyright: (c) 2014-2016 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

import pytest

from weppy.testing.env import EnvironBuilder
from weppy.sessions import SessionCookieManager


@pytest.fixture(scope='module')
def current():
    from weppy.globals import current
    builder = EnvironBuilder()
    current.initialize(builder.get_environ())
    return current


def test_session_cookie(current):
    session_cookie = SessionCookieManager(
        key='sid',
        secure=True,
        domain='localhost'
    )
    assert session_cookie.key == 'sid'
    assert session_cookie.secure is True
    assert session_cookie.domain == 'localhost'

    session_cookie.open()
    assert current.session._expiration == 3600

    session_cookie.close()
    cookie = str(current.response.cookies)
    assert 'wpp_session_data_' in cookie
    assert 'Domain=localhost;' in cookie
    # Python 3.5 make Secure attribute in cookie capitalized
    assert 'secure' in cookie.lower()

    current.request.cookies = current.response.cookies
    session_cookie.open()
    assert current.session._expiration == 3600
