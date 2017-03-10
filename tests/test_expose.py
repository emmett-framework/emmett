# -*- coding: utf-8 -*-
"""
    tests.expose
    ----------------

    Test weppy expose module

    :copyright: (c) 2014-2016 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

import pytest
from weppy import App
from weppy.http import HTTP
from weppy.expose import url
from weppy.testing.env import EnvironBuilder


@pytest.fixture(scope='module')
def app():
    app = App(__name__)
    app.languages = ['en', 'it']
    app.language_default = 'en'
    app.language_force_on_url = True
    return app


def test_expose_valid_route(app):
    from weppy.globals import current
    builder = EnvironBuilder('/it/test_route')
    current.initialize(builder.get_environ())

    @app.route()
    def test_route():
        return 'Test Router'

    response = current.response
    app.route.dispatch()
    assert response.status == 200
    assert response.output == 'Test Router'
    assert current.request.language == 'it'


def test_expose_not_found_route(app):
    from weppy.globals import current
    builder = EnvironBuilder('/')
    current.initialize(builder.get_environ())

    @app.route()
    def test_route():
        return 'Test Router'

    with pytest.raises(HTTP) as excinfo:
        app.route.dispatch()
    assert excinfo.value.status_code == 404
    assert excinfo.value.body == [b'Resource not found\n']


def test_expose_exception_route(app):
    from weppy.globals import current
    builder = EnvironBuilder('/test_route')
    current.initialize(builder.get_environ())

    @app.route()
    def test_route():
        raise HTTP(404, 'Not found, dude')

    with pytest.raises(HTTP) as excinfo:
        app.route.dispatch()
    assert excinfo.value.status_code == 404
    assert excinfo.value.body == [b'Not found, dude']


def test_static_url(app):
    link = url('static', 'file')
    assert link == '/static/file'
    app.config.static_version_urls = True
    app.config.static_version = '1.0.0'
    link = url('static', 'js/foo.js', language='it')
    assert link == '/it/static/_1.0.0/js/foo.js'


def test_module_url(app):
    from weppy.globals import current
    builder = EnvironBuilder('/')
    current.initialize(builder.get_environ())
    current.request.language = 'it'

    @app.route('/test')
    def test_route():
        return 'Test Router'

    @app.route('/test2/<int:a>/<str:b>')
    def test_route2(a, b):
        return 'Test Router'

    @app.route('/test3/<int:a>/foo(/<str:b>)?(.<str:c>)?')
    def test_route3(a, b, c):
        return 'Test Router'

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
    link = url('test_route3', [2, 'bar', 'json'], {'foo': 'bar', 'bar': 'foo'})
    lsplit = link.split('?')
    assert lsplit[0] == '/it/test3/2/foo/bar.json'
    assert lsplit[1] in ['foo=bar&bar=foo', 'bar=foo&foo=bar']
