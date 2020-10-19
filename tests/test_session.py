# -*- coding: utf-8 -*-
"""
    tests.session
    -------------

    Test Emmett session module
"""

import pytest

from emmett.asgi.handlers import RequestContext
from emmett.ctx import current
from emmett.sessions import SessionManager
from emmett.testing.env import ScopeBuilder
from emmett.wrappers.request import Request
from emmett.wrappers.response import Response


class FakeRequestContext(RequestContext):
    def __init__(self, app, scope):
        self.request = Request(scope, None, None)
        self.response = Response()
        self.session = None


@pytest.fixture(scope='module')
def ctx():
    builder = ScopeBuilder()
    token = current._init_(FakeRequestContext(None, builder.get_data()[0]))
    yield current
    current._close_(token)


@pytest.mark.asyncio
async def test_session_cookie(ctx):
    session_cookie = SessionManager.cookies(
        key='sid',
        secure=True,
        domain='localhost',
        cookie_name='foo_session'
    )
    assert session_cookie.key == 'sid'
    assert session_cookie.secure is True
    assert session_cookie.domain == 'localhost'

    await session_cookie.open_request()
    assert ctx.session._expiration == 3600

    await session_cookie.close_request()
    cookie = str(ctx.response.cookies)
    assert 'foo_session' in cookie
    assert 'Domain=localhost;' in cookie
    assert 'secure' in cookie.lower()

    ctx.request.cookies = ctx.response.cookies
    await session_cookie.open_request()
    assert ctx.session._expiration == 3600
