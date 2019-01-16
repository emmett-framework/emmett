# -*- coding: utf-8 -*-
"""
    tests.session
    ----------------

    Test weppy session module

    :copyright: (c) 2014-2016 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

import pytest

from weppy.asgi.handlers import RequestContext
from weppy.sessions import SessionManager
from weppy.testing.env import ScopeBuilder
from weppy.wrappers.request import Request
from weppy.wrappers.response import Response


class FakeRequestContext(RequestContext):
    def __init__(self, app, scope):
        self.request = Request(scope)
        self.response = Response()
        self.session = None


@pytest.fixture(scope='module')
def current():
    from weppy.ctx import current
    builder = ScopeBuilder()
    token = current._init_(FakeRequestContext, None, builder.get_data()[0])
    yield current
    current._close_(token)


@pytest.mark.asyncio
async def test_session_cookie(current):
    session_cookie = SessionManager.cookies(
        key='sid',
        secure=True,
        domain='localhost',
        cookie_name='foo_session'
    )
    assert session_cookie.key == 'sid'
    assert session_cookie.secure is True
    assert session_cookie.domain == 'localhost'

    await session_cookie.open()
    assert current.session._expiration == 3600

    await session_cookie.close()
    cookie = str(current.response.cookies)
    assert 'foo_session' in cookie
    assert 'Domain=localhost;' in cookie
    assert 'secure' in cookie.lower()

    current.request.cookies = current.response.cookies
    await session_cookie.open()
    assert current.session._expiration == 3600
