# -*- coding: utf-8 -*-
"""
    tests.translator
    ----------------

    Test weppy translator module

    :copyright: (c) 2015 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

from weppy import App, T
from weppy.globals import current


def _make_translation(language):
    return str(T('partly cloudy', language=language))


def test_translation():
    app = App(__name__)
    current._language = 'en'
    assert _make_translation('it') == 'nuvolosità variabile'
    assert _make_translation('de') == 'teilweise bewölkt'
    assert _make_translation('ru') == 'переменная облачность'
