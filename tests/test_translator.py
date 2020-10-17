# -*- coding: utf-8 -*-
"""
    tests.translator
    ----------------

    Test Emmett translator module
"""

import pytest

from emmett import App
from emmett.ctx import current
from emmett.locals import T


@pytest.fixture(scope='module')
def app():
    return App(__name__)


def _make_translation(language):
    return str(T('partly cloudy', lang=language))


def test_translation(app):
    current.language = 'en'
    assert _make_translation('it') == 'nuvolosità variabile'
    assert _make_translation('de') == 'teilweise bewölkt'
    assert _make_translation('ru') == 'переменная облачность'
