# -*- coding: utf-8 -*-
"""
    weppy.wsgi
    ----------

    Provide error, static and dynamic handlers for wsgi.

    :copyright: (c) 2015 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

import os
import sys
import re
from datetime import datetime

from .http import HTTP
from .stream import stream_file_handler

REGEX_STATIC = re.compile('^/(?P<l>\w+/)?static/(?P<v>_\d+\.\d+\.\d+/)?(?P<f>.*?)$')
REGEX_WEPPY = re.compile('^/__weppy__/(?P<f>.*?)$')
REGEX_RANGE = re.compile('^\s*(?P<start>\d*).*(?P<stop>\d*)\s*$')


def dynamic_handler(app, environ, start_response):
    try:
        #: init current
        from .globals import current
        environ["wpp.application"] = app.name
        environ["wpp.apppath"] = app.root_path
        environ["wpp.appnow"] = app.now_reference
        current.initialize(environ)
        #: dispatch request
        response = current.response
        app.expose.dispatch()
        #: build HTTP response
        http = HTTP(response.status, response.output, response.headers,
                    response.cookies)
    except HTTP:
        #: catch HTTP exceptions
        http = sys.exc_info()[1]
        #: render error with handlers if in app
        error_handler = app.error_handlers.get(http.status_code)
        if error_handler:
            output = error_handler()
            http = HTTP(http.status_code, output, http.headers)
        #: store cookies
        if response.cookies:
            chead = http.cookies2header(response.cookies)
            http.headers += chead
    return http.to(environ, start_response)


def static_handler(app, environ, start_response):
    path_info = environ['PATH_INFO']
    #: handle weppy assets (helpers)
    fw_match = REGEX_WEPPY.match(path_info)
    if fw_match:
        filename = fw_match.group('f')
        static_file = os.path.join(
            os.path.dirname(__file__), 'assets', filename)
        #: avoid exposing html files
        if os.path.splitext(static_file)[1] == 'html':
            return HTTP(404).to(environ, start_response)
        return stream_file_handler(
            environ, start_response, static_file)
    #: match and process static requests
    static_match = REGEX_STATIC.match(path_info)
    if static_match:
        #: process with language urls if required
        if app.language_force_on_url:
            lang, version, filename = static_match.group('l', 'v', 'f')
            static_file = os.path.join(app.static_path, filename)
            if lang:
                lang_file = os.path.join(app.static_path, lang, filename)
                if os.path.exists(lang_file):
                    static_file = lang_file
        #: process without language urls
        else:
            version, filename = static_match.group('v', 'f')
            static_file = os.path.join(app.static_path, filename)
        return stream_file_handler(
            environ, start_response, static_file, version)
    #: process dynamic requests
    else:
        return dynamic_handler(app, environ, start_response)


def error_handler(app, environ, start_response):
    ## TODO
    ## store in tickets based on application setting
    environ['wpp.now.utc'] = datetime.utcnow()
    environ['wpp.now.local'] = datetime.now()
    try:
        return static_handler(app, environ, start_response)
    except Exception:
        if app.debug:
            from .debug import smart_traceback, debug_handler
            tb = smart_traceback(app)
            body = debug_handler(tb)
        else:
            body = None
            custom_handler = app.error_handlers.get(500)
            if custom_handler:
                try:
                    body = custom_handler()
                except:
                    pass
            if not body:
                body = '<html><body>Internal error</body></html>'
        app.log.exception('Application exception:')
        return HTTP(500, body).to(environ, start_response)
