# -*- coding: utf-8 -*-
"""
    weppy.dal.adapters
    ------------------

    Provides adapters facilities for dal.

    :copyright: (c) 2014-2016 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

from pydal.adapters import adapters
from pydal.adapters.postgres import (
    Postgre, PostgrePsyco, PostgrePG8000,
    PostgreNew, PostgrePsycoNew, PostgrePG8000New,
    PostgreBoolean, PostgrePsycoBoolean, PostgrePG8000Boolean
)


adapters._registry_.update({
    'postgres': PostgreBoolean,
    'postgres:psycopg2': PostgrePsycoBoolean,
    'postgres:pg8000': PostgrePG8000Boolean,
    'postgres2': PostgreNew,
    'postgres2:psycopg2': PostgrePsycoNew,
    'postgres2:pg8000': PostgrePG8000New,
    'postgres3': Postgre,
    'postgres3:psycopg2': PostgrePsyco,
    'postgres3:pg8000': PostgrePG8000
})
