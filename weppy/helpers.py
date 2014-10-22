# -*- coding: utf-8 -*-
"""
    weppy.helpers
    -------------

    Provides helping methods for applications.

    :copyright: (c) 2014 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""


def abort(code):
    from .http import HTTP
    raise HTTP(code)


def stream_file(db, name):
    import re
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
    except IOError:
        abort(404)
    from .globals import request, response
    from .stream import streamer
    raise streamer(request.environ, fullfilename, headers=response.headers)


def flash(message, category='message'):
    """Flashes a message to the next request.  In order to remove the
    flashed message from the session and to display it to the user,
    the template has to call :func:`get_flashed_messages`.

    .. versionchanged:: 0.3
       `category` parameter added.

    :param message: the message to be flashed.
    :param category: the category for the message.  The following values
                     are recommended: ``'message'`` for any kind of message,
                     ``'error'`` for errors, ``'info'`` for information
                     messages and ``'warning'`` for warnings.  However any
                     kind of string can be used as category.
    """
    from .globals import session
    #flashes = session.get('_flashes', [])
    if session._flashes is None:
        session._flashes = []
    session._flashes.append((category, message))
    #session['_flashes'] = flashes


def get_flashed_messages(with_categories=False, category_filter=[]):
    """Pulls all flashed messages from the session and returns them.
    Further calls in the same request to the function will return
    the same messages.  By default just the messages are returned,
    but when `with_categories` is set to `True`, the return value will
    be a list of tuples in the form ``(category, message)`` instead.

    Filter the flashed messages to one or more categories by providing those
    categories in `category_filter`.  This allows rendering categories in
    separate html blocks.  The `with_categories` and `category_filter`
    arguments are distinct:

    * `with_categories` controls whether categories are returned with message
      text (`True` gives a tuple, where `False` gives just the message text).
    * `category_filter` filters the messages down to only those matching the
      provided categories.

    :param with_categories: set to `True` to also receive categories.
    :param category_filter: whitelist of categories to limit return values
    """
    from .globals import session
    try:
        flashes = session._flashes or []
        if category_filter:
            flashes = list(filter(lambda f: f[0] in category_filter, flashes))
        del session._flashes
        if not with_categories:
            return [x[1] for x in flashes]
    except:
        flashes = []
    return flashes


def load_component(url, target=None, content='loading...'):
    from .tags import tag
    attr = {}
    #target = target or 'c'+str(random.random())[2:]
    if target:
        attr['_id'] = target
    #component = "$.weppy.component('%s','%s');" % (url, target)
    attr['_data-wpp_remote'] = url
    return tag.div(content, **attr)
