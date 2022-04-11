# -*- coding: utf-8 -*-
"""
    tests.templates
    ---------------

    Test Emmett templating module
"""

import pytest

from helpers import current_ctx
from emmett import App


@pytest.fixture(scope='module')
def app():
    app = App(__name__)
    app.config.templates_escape = 'all'
    app.config.templates_adjust_indent = False
    app.config.templates_auto_reload = True
    return app


def test_helpers(app):
    templater = app.templater
    r = templater._render(source="{{ include_helpers }}")
    assert r == '<script type="text/javascript" ' + \
        'src="/__emmett__/jquery.min.js"></script>' + \
        '<script type="text/javascript" ' + \
        'src="/__emmett__/helpers.js"></script>'


def test_meta(app):
    with current_ctx('/', app) as ctx:
        ctx.response.meta.foo = "bar"
        ctx.response.meta_prop.foo = "bar"
        templater = app.templater
        r = templater._render(
            source="{{ include_meta }}",
            context={'current': ctx})
        assert r == '<meta name="foo" content="bar" />' + \
            '<meta property="foo" content="bar" />'


def test_static(app):
    templater = app.templater
    s = "{{include_static 'foo.js'}}\n{{include_static 'bar.css'}}"
    r = templater._render(source=s)
    assert r == '<script type="text/javascript" src="/static/foo.js">' + \
        '</script>\n<link rel="stylesheet" href="/static/bar.css" ' + \
        'type="text/css" />'


rendered_value = """
<!DOCTYPE html>
<html>
    <head>
        <title>Test</title>
        {helpers}
        <link rel="stylesheet" href="/static/style.css" type="text/css" />
    </head>
    <body>
        <div class="page">
            <a href="/" class="title"><h1>Test</h1></a>
            <div class="nav">
                <a href="/">nuvolosit&#224; variabile</a>
            </div>
            <ul class="posts">
                <li>
                    <h2>foo</h2>
                    <hr />
                </li>
                <li>
                    <h2>bar</h2>
                    <hr />
                </li>
            </ul>
        </div>
    </body>
</html>""".format(
    helpers="".join([
        f'<script type="text/javascript" src="/__emmett__/{name}"></script>'
        for name in ["jquery.min.js", "helpers.js"]
    ])
)


def test_render(app):
    with current_ctx('/', app) as ctx:
        ctx.language = 'it'
        r = app.templater.render(
            'test.html', {
                'current': ctx, 'posts': [{'title': 'foo'}, {'title': 'bar'}]
            }
        )
        assert "\n".join([l.strip() for l in r.splitlines() if l.strip()]) == \
            "\n".join([l.strip() for l in rendered_value[1:].splitlines()])
