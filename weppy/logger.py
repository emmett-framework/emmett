# -*- coding: utf-8 -*-
"""
    weppy.logger
    ------------

    Provides logging utitilites for weppy applications.

    :copyright: (c) 2014-2017 by Giovanni Barillari

    Based on the code of Flask (http://flask.pocoo.org)
    :copyright: (c) 2014 by Armin Ronacher.

    :license: BSD, see LICENSE for more details.
"""

from __future__ import absolute_import
import os
from threading import Lock
from logging import getLogger, StreamHandler, Formatter, getLoggerClass, DEBUG
from logging.handlers import RotatingFileHandler
from .datastructures import sdict

_logger_lock = Lock()

_levels = {
    'debug': 10,
    'info': 20,
    'warning': 30,
    'error': 40,
    'critical': 50
}

_def_log_config = sdict(
    production=sdict(
        max_size=5 * 1024 * 1024,
        file_no=4,
        level='warning',
        format='[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
        on_app_debug=False))

_debug_log_format = (
    '> %(levelname)s in %(module)s [%(pathname)s:%(lineno)d]:\n' +
    '%(message)s'
)


def create_logger(app):
    Logger = getLoggerClass()

    class DebugLogger(Logger):
        def getEffectiveLevel(x):
            if x.level == 0 and app.debug:
                return DEBUG
            return Logger.getEffectiveLevel(x)

    class DebugHandler(StreamHandler):
        def emit(x, record):
            StreamHandler.emit(x, record) if app.debug else None

    class DebugRFHandler(RotatingFileHandler):
        def emit(x, record):
            RotatingFileHandler.emit(x, record) if app.debug else None

    class ProdRFHandler(RotatingFileHandler):
        def emit(x, record):
            RotatingFileHandler.emit(x, record) if not app.debug else None

    # init the console debug handler
    debug_handler = DebugHandler()
    debug_handler.setLevel(DEBUG)
    debug_handler.setFormatter(Formatter(_debug_log_format))
    logger = getLogger(app.logger_name)
    # just in case that was not a new logger, get rid of all the handlers
    # already attached to it.
    del logger.handlers[:]
    logger.__class__ = DebugLogger
    logger.addHandler(debug_handler)
    # load application logging config
    app_logs = app.config.logging
    if not app_logs:
        app_logs = _def_log_config
    for lname, lconf in app_logs.items():
        lfile = os.path.join(app.root_path, 'logs', lname + '.log')
        max_size = lconf.max_size or _def_log_config.production.max_size
        file_no = lconf.file_no or _def_log_config.production.file_no
        level = _levels.get(lconf.level or 'warning', _levels.get('warning'))
        lformat = lconf.format or _def_log_config.production.format
        on_app_debug = lconf.on_app_debug
        if on_app_debug:
            handler = DebugRFHandler(lfile, maxBytes=max_size,
                                     backupCount=file_no)
        else:
            handler = ProdRFHandler(lfile, maxBytes=max_size,
                                    backupCount=file_no)
        handler.setLevel(level)
        handler.setFormatter(Formatter(lformat))
        logger.addHandler(handler)
    return logger
