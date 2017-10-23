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
from weppy.sessions import SessionManager


@pytest.fixture(scope='module')
def current():
    from weppy.globals import current
    builder = EnvironBuilder()
    current.initialize(builder.get_environ())
    return current


def test_session_cookie(current):
    session_cookie = SessionManager.cookies(
        key='sid',
        secure=True,
        domain='localhost',
        cookie_name='foo_session'
    )
    assert session_cookie.key == 'sid'
    assert session_cookie.secure is True
    assert session_cookie.domain == 'localhost'

    session_cookie.open()
    assert current.session._expiration == 3600

    session_cookie.close()
    cookie = str(current.response.cookies)
    assert 'foo_session' in cookie
    assert 'Domain=localhost;' in cookie
    assert 'secure' in cookie.lower()

    current.request.cookies = current.response.cookies
    session_cookie.open()
    assert current.session._expiration == 3600
