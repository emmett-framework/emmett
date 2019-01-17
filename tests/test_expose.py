# -*- coding: utf-8 -*-
"""
    tests.expose
    ----------------

    Test weppy expose module

    :copyright: (c) 2014-2016 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

import pytest

from contextlib import contextmanager

from helpers import FakeRequestContext
from weppy import App
from weppy.ctx import current
from weppy.expose import url
from weppy.http import HTTP
from weppy.testing.env import ScopeBuilder


@contextmanager
def current_ctx(path):
    builder = ScopeBuilder(path)
    token = current._init_(FakeRequestContext, None, builder.get_data()[0])
    yield current
    current._close_(token)


@pytest.fixture(scope='module')
def app():
    app = App(__name__)
    app.languages = ['en', 'it']
    app.language_default = 'en'
    app.language_force_on_url = True
    return app


@pytest.mark.asyncio
async def test_expose_valid_route(app):
    @app.route()
    def test_route():
        return 'Test Router'

    with current_ctx('/it/test_route') as ctx:
        response = await app.route.dispatch()
        assert response.status_code == ctx.response.status == 200
        assert response.body == 'Test Router'
        assert ctx.request.language == 'it'


@pytest.mark.asyncio
async def test_expose_not_found_route(app):
    @app.route()
    def test_route():
        return 'Test Router'

    with current_ctx('/') as ctx:
        with pytest.raises(HTTP) as excinfo:
            await app.route.dispatch()
        assert excinfo.value.status_code == 404
        assert excinfo.value.body == 'Resource not found\n'


@pytest.mark.asyncio
async def test_expose_exception_route(app):
    @app.route()
    def test_route():
        raise HTTP(404, 'Not found, dude')

    with current_ctx('/test_route') as ctx:
        with pytest.raises(HTTP) as excinfo:
            await app.route.dispatch()
        assert excinfo.value.status_code == 404
        assert excinfo.value.body == 'Not found, dude'


def test_static_url(app):
    link = url('static', 'file')
    assert link == '/static/file'
    app.config.static_version_urls = True
    app.config.static_version = '1.0.0'
    link = url('static', 'js/foo.js', language='it')
    assert link == '/it/static/_1.0.0/js/foo.js'


def test_module_url(app):
    @app.route('/test')
    def test_route():
        return 'Test Router'

    @app.route('/test2/<int:a>/<str:b>')
    def test_route2(a, b):
        return 'Test Router'

    @app.route('/test3/<int:a>/foo(/<str:b>)?(.<str:c>)?')
    def test_route3(a, b, c):
        return 'Test Router'

    with current_ctx('/') as ctx:
        ctx.request.language = 'it'
        link = url('test_route')
        assert link == '/it/test'
        link = url('test_route2')
        assert link == '/it/test2'
        link = url('test_route2', [2])
        assert link == '/it/test2/2'
        link = url('test_route2', [2, 'foo'])
        assert link == '/it/test2/2/foo'
        link = url('test_route3')
        assert link == '/it/test3'
        link = url('test_route3', [2])
        assert link == '/it/test3/2/foo'
        link = url('test_route3', [2, 'bar'])
        assert link == '/it/test3/2/foo/bar'
        link = url('test_route3', [2, 'bar', 'json'])
        assert link == '/it/test3/2/foo/bar.json'
        link = url(
            'test_route3', [2, 'bar', 'json'], {'foo': 'bar', 'bar': 'foo'})
        lsplit = link.split('?')
        assert lsplit[0] == '/it/test3/2/foo/bar.json'
        assert lsplit[1] in ['foo=bar&bar=foo', 'bar=foo&foo=bar']


@pytest.mark.asyncio
async def test_global_url_prefix(app):
    app.route._bind_app_(app, 'foo')

    @app.route('/test')
    def test_route():
        return 'Test Router'

    with current_ctx('/') as ctx:
        app.config.static_version_urls = False
        ctx.request.language = 'en'

        link = url('test_route')
        assert link == '/foo/test'

        link = url('static', 'js/foo.js')
        assert link == '/foo/static/js/foo.js'

        app.config.static_version_urls = True
        app.config.static_version = '1.0.0'

        link = url('static', 'js/foo.js')
        assert link == '/foo/static/_1.0.0/js/foo.js'

        app.config.static_version_urls = False
        ctx.request.language = 'it'

        link = url('test_route')
        assert link == '/foo/it/test'

        link = url('static', 'js/foo.js')
        assert link == '/foo/it/static/js/foo.js'

        app.config.static_version_urls = True
        app.config.static_version = '1.0.0'

        link = url('static', 'js/foo.js')
        assert link == '/foo/it/static/_1.0.0/js/foo.js'
