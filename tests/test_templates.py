# -*- coding: utf-8 -*-
"""
    tests.templates
    ---------------

    Test weppy templating module

    :copyright: (c) 2015 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

import pytest
from weppy import App
from weppy.templating.core import Templater


@pytest.fixture(scope='module')
def app():
    app = App(__name__)
    return app


def test_define(app):
    templater = Templater(app)
    assert templater.render(source='{{=1}}', filename='test1') == '1'
    assert templater.render(
        source='{{=a}}', filename='test2',
        context={'a': 'nuvolosità variabile'}
    ) == 'nuvolosità variabile'
    assert templater.render(
        source='{{=a}}', path='templates', filename='test3',
        context={'a': u'nuvolosità variabile'}
    ) == 'nuvolosità variabile'
    assert templater.render(
        source='{{=a}}', filename='test4',
        context={'a': [i for i in range(0, 5)]}
    ) == "[0, 1, 2, 3, 4]"


def test_blocks(app):
    pass


def test_superblock(app):
    pass


def test_include(app):
    pass


def test_extend(app):
    pass


def test_helpers(app):
    pass


def test_meta(app):
    pass


def test_static(app):
    pass


def test_render(app):
    pass
