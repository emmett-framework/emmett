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

    try:
        app.route.dispatch()
    except HTTP as exc:
        assert exc.status_code == 404
        assert exc.body == [b'Invalid action\n']


def test_expose_exception_route(app):
    from weppy.globals import current
    builder = EnvironBuilder('/test_route')
    current.initialize(builder.get_environ())

    @app.route()
    def test_route():
        raise HTTP(404, 'Not found')

    try:
        app.route.dispatch()
    except HTTP as exc:
        assert exc.status_code == 404
        assert exc.body == [b'Not found']


def test_static_url():
    link = url('static', 'file')
    assert link == '/static/file'


def test_module_url(app):
    from weppy.globals import current
    builder = EnvironBuilder('/')
    current.initialize(builder.get_environ())
    current.request.language = 'it'

    @app.route()
    def test_route():
        return 'Test Router'

    link = url('test_route')
    assert link == '/it/test_route'
