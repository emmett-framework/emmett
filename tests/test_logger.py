# -*- coding: utf-8 -*-
import os
import shutil
import logging

import pytest
from weppy import App, logger, sdict


def teardown_module():
    root = os.path.dirname(__file__)
    shutil.rmtree(os.path.join(root, 'logs'))
    shutil.rmtree(os.path.join(root, 'static'))


def _call_create_logger(app):
    return logger.create_logger(app)


def test_user_assign_valid_level():
    app = App(__name__)
    app.config.logging.pytest = sdict(
        level='info'
    )
    result = _call_create_logger(app)
    assert result.handlers[-1].level == logging.INFO


def test_user_assign_invaild_level():
    app = App(__name__)
    app.config.logging.pytest = sdict(
        level='invalid'
    )
    result = _call_create_logger(app)
    assert result.handlers[-1].level == logging.WARNING


def test_user_no_assign_level():
    app = App(__name__)
    app.config.logging.pytest = sdict()
    result = _call_create_logger(app)
    assert result.handlers[-1].level == logging.WARNING
