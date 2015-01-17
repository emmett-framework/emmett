# -*- coding: utf-8 -*-
"""
    weppy.helpers
    -------------

    Provides helping methods for applications.

    :copyright: (c) 2015 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""


def abort(code):
    from .http import HTTP
    raise HTTP(code)


def stream_file(path):
    import os
    from .globals import request, response
    from .expose import Expose
    from .stream import streamer
    fullfilename = os.path.join(Expose.application.root_path, path)
    raise streamer(request.environ, fullfilename, headers=response.headers)


def stream_dbfile(db, name):
    import re
    from pydal.exceptions import NotAuthorizedException, NotFoundException
    items = re.compile('(?P<table>.*?)\.(?P<field>.*?)\..*').match(name)
    if not items:
        abort(404)
    (t, f) = (items.group('table'), items.group('field'))
    try:
        field = db[t][f]
    except AttributeError:
        abort(404)
    try:
        (filename, fullfilename) = field.retrieve(name, nameonly=True)
    except NotAuthorizedException:
        abort(403)
    except NotFoundException:
        abort(404)
    except IOError:
        abort(404)
    from .globals import request, response
    from .stream import streamer
    raise streamer(request.environ, fullfilename, headers=response.headers)


def flash(message, category='message'):
    #: Flashes a message to the next request.
    from .globals import session
    if session._flashes is None:
        session._flashes = []
    session._flashes.append((category, message))


def get_flashed_messages(with_categories=False, category_filter=[]):
    #: Pulls flashed messages from the session and returns them.
    #  By default just the messages are returned, but when `with_categories`
    #  is set to `True`, the return value will be a list of tuples in the
    #  form `(category, message)` instead.
    from .globals import session
    try:
        flashes = list(session._flashes or [])
        if category_filter:
            flashes = list(filter(lambda f: f[0] in category_filter, flashes))
        for el in flashes:
            session._flashes.remove(el)
        if not with_categories:
            return [x[1] for x in flashes]
    except:
        flashes = []
    return flashes


def load_component(url, target=None, content='loading...'):
    from .tags import tag
    attr = {}
    if target:
        attr['_id'] = target
    attr['_data-wpp_remote'] = url
    return tag.div(content, **attr)
