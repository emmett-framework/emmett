# -*- coding: utf-8 -*-
"""
    weppy.testing.client
    --------------------

    Provides base classes for testing suite.

    :copyright: (c) 2014-2017 by Giovanni Barillari

    Several parts of this code comes from Werkzeug.
    :copyright: (c) 2015 by Armin Ronacher.

    :license: BSD, see LICENSE for more details.
"""

import copy
from itertools import chain
from .._compat import reraise, text_type, to_native
from .._internal import ClosingIterator
from ..utils import cachedprop
from .env import EnvironBuilder
from .helpers import TestCookieJar, Headers
from .urls import get_host, url_parse, url_unparse


class ClientContext(object):
    def __init__(self):
        from ..globals import current, Request, Response
        self.request = Request(current.request.environ)
        self.response = Response(current.request.environ)
        self.response.__dict__.update(current.response.__dict__)
        self.session = copy.deepcopy(current.session)
        self.T = current.T

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, tb):
        pass


class ClientResponse(object):
    def __init__(self, raw, status, headers):
        self.raw = raw
        self.status = status
        self.headers = headers
        self._close = lambda: None
        self._context = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, tb):
        pass

    @cachedprop
    def context(self):
        return ClientContext()

    @cachedprop
    def data(self):
        self._ensure_sequence()
        rv = b''.join(self.iter_encoded())
        return to_native(rv)

    @property
    def is_sequence(self):
        return isinstance(self.raw, (tuple, list))

    def _ensure_sequence(self, mutable=False):
        if self.is_sequence:
            # if we need a mutable object, we ensure it's a list.
            if mutable and not isinstance(self.response, list):
                self.response = list(self.response)
            return
        self.make_sequence()

    def make_sequence(self):
        if not self.is_sequence:
            close = getattr(self.raw, 'close', None)
            self.raw = list(self.iter_encoded())
            self._close = close

    def close(self):
        if hasattr(self.raw, 'close'):
            self.response.close()
        self._close()

    def iter_encoded(self, charset='utf-8'):
        for item in self.raw:
            if isinstance(item, text_type):
                yield item.encode(charset)
            else:
                yield item


class WeppyTestClient(object):
    """This class allows to send requests to a wrapped application."""

    def __init__(self, application, response_wrapper=ClientResponse,
                 use_cookies=True, allow_subdomain_redirects=False):
        self.application = application
        self.response_wrapper = response_wrapper
        if use_cookies:
            self.cookie_jar = TestCookieJar()
        else:
            self.cookie_jar = None
        self.allow_subdomain_redirects = allow_subdomain_redirects

    # def set_cookie(self, server_name, key, value='', max_age=None,
    #                expires=None, path='/', domain=None, secure=None,
    #                httponly=False, charset='utf-8'):
    #     """Sets a cookie in the client's cookie jar.  The server name
    #     is required and has to match the one that is also passed to
    #     the open call.
    #     """
    #     assert self.cookie_jar is not None, 'cookies disabled'
    #     header = dump_cookie(key, value, max_age, expires, path, domain,
    #                          secure, httponly, charset)
    #     environ = create_environ(path, base_url='http://' + server_name)
    #     headers = [('Set-Cookie', header)]
    #     self.cookie_jar.extract_wsgi(environ, headers)

    # def delete_cookie(self, server_name, key, path='/', domain=None):
    #     """Deletes a cookie in the test client."""
    #     self.set_cookie(server_name, key, expires=0, max_age=0,
    #                     path=path, domain=domain)

    def run_wsgi_app(self, environ, buffered=False):
        """Runs the wrapped WSGI app with the given environment."""
        if self.cookie_jar is not None:
            self.cookie_jar.inject_wsgi(environ)
        rv = run_wsgi_app(self.application, environ, buffered=buffered)
        if self.cookie_jar is not None:
            self.cookie_jar.extract_wsgi(environ, rv[2])
        return rv

    def resolve_redirect(self, response, new_loc, environ, buffered=False):
        """Resolves a single redirect and triggers the request again
        directly on this redirect client.
        """
        scheme, netloc, script_root, qs, anchor = url_parse(new_loc)
        base_url = url_unparse((scheme, netloc, '', '', '')).rstrip('/') + '/'

        cur_name = netloc.split(':', 1)[0].split('.')
        real_name = get_host(environ).rsplit(':', 1)[0].split('.')

        if len(cur_name) == 1 and not cur_name[0]:
            allowed = True
        else:
            if self.allow_subdomain_redirects:
                allowed = cur_name[-len(real_name):] == real_name
            else:
                allowed = cur_name == real_name

        if not allowed:
            raise RuntimeError('%r does not support redirect to '
                               'external targets' % self.__class__)

        status_code = int(response[1].split(None, 1)[0])
        if status_code == 307:
            method = environ['REQUEST_METHOD']
        else:
            method = 'GET'

        # For redirect handling we temporarily disable the response
        # wrapper.  This is not threadsafe but not a real concern
        # since the test client must not be shared anyways.
        old_response_wrapper = self.response_wrapper
        self.response_wrapper = None
        try:
            return self.open(path=script_root, base_url=base_url,
                             query_string=qs, as_tuple=True,
                             buffered=buffered, method=method)
        finally:
            self.response_wrapper = old_response_wrapper

    def open(self, *args, **kwargs):
        """Takes the same arguments as the :class:`EnvironBuilder` class with
        some additions:  You can provide a :class:`EnvironBuilder` or a WSGI
        environment as only argument instead of the :class:`EnvironBuilder`
        arguments and two optional keyword arguments (`as_tuple`, `buffered`)
        that change the type of the return value or the way the application is
        executed.

        Additional parameters:

        :param as_tuple: Returns a tuple in the form ``(environ, result)``
        :param buffered: Set this to True to buffer the application run.
                         This will automatically close the application for
                         you as well.
        :param follow_redirects: Set this to True if the `Client` should
                                 follow HTTP redirects.
        """
        as_tuple = kwargs.pop('as_tuple', False)
        buffered = kwargs.pop('buffered', False)
        follow_redirects = kwargs.pop('follow_redirects', False)
        environ = None
        if not kwargs and len(args) == 1:
            if isinstance(args[0], EnvironBuilder):
                environ = args[0].get_environ()
            elif isinstance(args[0], dict):
                environ = args[0]
        if environ is None:
            builder = EnvironBuilder(*args, **kwargs)
            try:
                environ = builder.get_environ()
            finally:
                builder.close()

        response = self.run_wsgi_app(environ, buffered=buffered)

        # handle redirects
        redirect_chain = []
        while 1:
            status_code = int(response[1].split(None, 1)[0])
            if status_code not in (301, 302, 303, 305, 307) \
               or not follow_redirects:
                break
            new_location = response[2]['location']
            if new_location.startswith('/'):
                new_location = (
                    environ['wsgi.url_scheme'] + "://" +
                    environ['HTTP_HOST'] + new_location)
            new_redirect_entry = (new_location, status_code)
            if new_redirect_entry in redirect_chain:
                raise Exception('loop detected')
            redirect_chain.append(new_redirect_entry)
            environ, response = self.resolve_redirect(response, new_location,
                                                      environ,
                                                      buffered=buffered)

        if self.response_wrapper is not None:
            response = self.response_wrapper(*response)
        if as_tuple:
            return environ, response
        return response

    def get(self, *args, **kw):
        """Like open but method is enforced to GET."""
        kw['method'] = 'GET'
        return self.open(*args, **kw)

    def patch(self, *args, **kw):
        """Like open but method is enforced to PATCH."""
        kw['method'] = 'PATCH'
        return self.open(*args, **kw)

    def post(self, *args, **kw):
        """Like open but method is enforced to POST."""
        kw['method'] = 'POST'
        return self.open(*args, **kw)

    def head(self, *args, **kw):
        """Like open but method is enforced to HEAD."""
        kw['method'] = 'HEAD'
        return self.open(*args, **kw)

    def put(self, *args, **kw):
        """Like open but method is enforced to PUT."""
        kw['method'] = 'PUT'
        return self.open(*args, **kw)

    def delete(self, *args, **kw):
        """Like open but method is enforced to DELETE."""
        kw['method'] = 'DELETE'
        return self.open(*args, **kw)

    def options(self, *args, **kw):
        """Like open but method is enforced to OPTIONS."""
        kw['method'] = 'OPTIONS'
        return self.open(*args, **kw)

    def trace(self, *args, **kw):
        """Like open but method is enforced to TRACE."""
        kw['method'] = 'TRACE'
        return self.open(*args, **kw)

    def __repr__(self):
        return '<%s %r>' % (
            self.__class__.__name__,
            self.application
        )


def create_environ(*args, **kwargs):
    builder = EnvironBuilder(*args, **kwargs)
    try:
        return builder.get_environ()
    finally:
        builder.close()


def run_wsgi_app(app, environ, buffered=False):
    response = []
    buffer = []

    def start_response(status, headers, exc_info=None):
        if exc_info is not None:
            reraise(*exc_info)
        response[:] = [status, headers]
        return buffer.append

    app_rv = app(environ, start_response)
    close_func = getattr(app_rv, 'close', None)
    app_iter = iter(app_rv)

    # when buffering we emit the close call early and convert the
    # application iterator into a regular list
    if buffered:
        try:
            app_iter = list(app_iter)
        finally:
            if close_func is not None:
                close_func()

    # otherwise we iterate the application iter until we have a response, chain
    # the already received data with the already collected data and wrap it in
    # a new `ClosingIterator` if we need to restore a `close` callable from the
    # original return value.
    else:
        while not response:
            buffer.append(next(app_iter))
        if buffer:
            app_iter = chain(buffer, app_iter)
        if close_func is not None and app_iter is not app_rv:
            app_iter = ClosingIterator(app_iter, close_func)

    return app_iter, response[0], Headers(response[1])
