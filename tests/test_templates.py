# -*- coding: utf-8 -*-
"""
    tests.templates
    ---------------

    Test weppy templating module

    :copyright: (c) 2014-2016 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

import pytest
from datetime import datetime
from weppy import App
from weppy.globals import current


@pytest.fixture(scope='module')
def app():
    app = App(__name__)
    app.config.templates_escape = 'all'
    return app


def test_define(app):
    templater = app.templater
    assert templater._render(source='{{=1}}', filename='test1') == '1'
    assert templater._render(
        source='{{=a}}', filename='test2',
        context={'a': 'nuvolosità variabile'}
    ) == 'nuvolosit&#224; variabile'
    assert templater._render(
        source='{{=a}}', path='templates', filename='test3',
        context={'a': u'nuvolosità variabile'}
    ) == 'nuvolosit&#224; variabile'
    assert templater._render(
        source='{{=a}}', filename='test4',
        context={'a': [i for i in range(0, 5)]}
    ) == "[0, 1, 2, 3, 4]"


# def test_superblock(app):
#     pass


def test_helpers(app):
    templater = app.templater
    r = templater._render(source="{{include_helpers}}", filename='testh')
    assert r == '<script type="text/javascript" ' + \
        'src="/__weppy__/jquery.min.js"></script>\n' + \
        '<script type="text/javascript" ' + \
        'src="/__weppy__/helpers.js"></script>'


def test_meta(app):
    current.initialize({
        'PATH_INFO': '/',
        'REQUEST_METHOD': 'GET',
        'HTTP_HOST': 'localhost',
        'wsgi.url_scheme': 'http',
        'wpp.now': datetime.utcnow(),
        'wpp.application': 'test'
    })
    current.response.meta.foo = "bar"
    current.response.meta_prop.foo = "bar"
    templater = app.templater
    r = templater._render(
        source="{{include_meta}}", filename='mtest',
        context={'current': current})
    assert r == '<meta name="foo" content="bar" />\n' + \
        '<meta property="foo" content="bar" />\n'


def test_static(app):
    templater = app.templater
    s = "{{include_static 'foo.js'}}\n{{include_static 'bar.css'}}"
    r = templater._render(source=s, filename="stest")
    assert r == '<script type="text/javascript" src="/static/foo.js">' + \
        '</script>\n<link rel="stylesheet" href="/static/bar.css" ' + \
        'type="text/css" />'


def test_pycode(app):
    templater = app.templater
    #: test if block
    s = "{{if a == 1:}}foo{{elif a == 2:}}bar{{else:}}foobar{{pass}}"
    r = templater._render(source=s, filename="ptest1", context={'a': 1})
    assert r == "foo"
    r = templater._render(source=s, filename="ptest1", context={'a': 2})
    assert r == "bar"
    r = templater._render(source=s, filename="ptest1", context={'a': 25})
    assert r == "foobar"
    #: test for block
    s = "{{for i in range(0, 5):}}{{=i}}\n{{pass}}"
    r = templater._render(source=s, filename="ptest2")
    assert r == "0\n1\n2\n3\n4\n"


rendered_value = """
<!DOCTYPE html>
<html>
    <head>
        <title>Test</title>
        <meta name="foo" content="bar" />
        <meta property="foo" content="bar" />
        <script type="text/javascript" src="/__weppy__/jquery.min.js"></script>
        <script type="text/javascript" src="/__weppy__/helpers.js"></script>
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
</html>
"""


def test_render(app):
    current.language = 'it'
    r = app.templater.render(
        app.template_path, 'test.html', {
            'current': current, 'posts': [{'title': 'foo'}, {'title': 'bar'}]
        }
    )
    assert "".join([l.strip() for l in r.splitlines()]) == \
        "".join([l.strip() for l in rendered_value.splitlines()])


# def test_cache(app):
#     pass
