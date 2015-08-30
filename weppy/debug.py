# -*- coding: utf-8 -*-
"""
    weppy.debug
    -----------

    Provides debugging utilities.

    :copyright: (c) 2015 by Giovanni Barillari

    Quite a lot of magic comes from Flask (http://flask.pocoo.org)
    :copyright: (c) 2014 by Armin Ronacher.

    :license: BSD, see LICENSE for more details.
"""

import traceback
import inspect
import os
import sys
from types import TracebackType, CodeType
from ._compat import PY2, reraise, iteritems
from .templating.helpers import TemplateError


# on pypy we can take advantage of transparent proxies
try:
    from __pypy__ import tproxy
except ImportError:
    tproxy = None


# how does the raise helper look like?
try:
    exec("raise TypeError, 'foo'")
except SyntaxError:
    raise_helper = 'raise __weppy_exception__[1]'
except TypeError:
    raise_helper = 'raise __weppy_exception__[0], __weppy_exception__[1]'


class TracebackFrameProxy(object):
    """Proxies a traceback frame."""

    def __init__(self, tb):
        self.tb = tb
        self._tb_next = None

    @property
    def tb_next(self):
        return self._tb_next

    def set_next(self, next):
        if tb_set_next is not None:
            try:
                tb_set_next(self.tb, next and next.tb or None)
            except Exception:
                # this function can fail due to all the hackery it does
                # on various python implementations.  We just catch errors
                # down and ignore them if necessary.
                pass
        self._tb_next = next

    #@property
    #def is_weppy_frame(self):
    #    return '__weppy_template__' in self.tb.tb_frame.f_globals

    def __getattr__(self, name):
        return getattr(self.tb, name)


class ProcessedTraceback(object):
    """Holds a weppy preprocessed traceback for printing or reraising."""

    def __init__(self, exc_type, exc_value, frames):
        assert frames, 'no frames for this traceback?'
        self.exc_type = exc_type
        self.exc_value = exc_value
        self.frames = frames

        # newly concatenate the frames (which are proxies)
        prev_tb = None
        for tb in self.frames:
            if prev_tb is not None:
                prev_tb.set_next(tb)
            prev_tb = tb
        prev_tb.set_next(None)

    def render_as_text(self, limit=None):
        """Return a string with the traceback."""
        lines = traceback.format_exception(self.exc_type, self.exc_value,
                                           self.frames[0], limit=limit)
        return ''.join(lines).rstrip()

    @property
    def exc_info(self):
        """Exception info tuple with a proxy around the frame objects."""
        return self.exc_type, self.exc_value, self.frames[0]

    @property
    def standard_exc_info(self):
        """Standard python exc_info for re-raising"""
        tb = self.frames[0]
        # the frame will be an actual traceback (or transparent proxy) if
        # we are on pypy or a python implementation with support for tproxy
        if type(tb) is not TracebackType:
            tb = tb.tb
        return self.exc_type, self.exc_value, tb


class Traceback(object):
    """Wraps a traceback."""

    def __init__(self, app, exc_type, exc_value, tb):
        self.app = app
        self.exc_type = exc_type
        self.exc_value = exc_value
        if not isinstance(exc_type, str):
            exception_type = exc_type.__name__
            if exc_type.__module__ not in ('__builtin__', 'exceptions'):
                exception_type = exc_type.__module__ + '.' + exception_type
        else:
            exception_type = exc_type
        self.exception_type = exception_type

        self.frames = []
        while tb:
            self.frames.append(Frame(self.app, exc_type, exc_value, tb))
            tb = tb.tb_next

    @property
    def exception(self):
        """String representation of the exception."""
        buf = traceback.format_exception_only(self.exc_type, self.exc_value)
        rv = ''.join(buf).strip()
        return rv.decode('utf-8', 'replace') if PY2 else rv

    def generate_plaintext_traceback(self):
        """Like the plaintext attribute but returns a generator"""
        yield u'Traceback (most recent call last):'
        for frame in self.frames:
            yield u'  File "%s", line %s, in %s' % (
                frame.filename,
                frame.lineno,
                frame.function_name
            )
            yield u'    ' + frame.current_line.strip()
        yield self.exception

    def generate_plain_tb_app(self):
        yield u'Traceback (most recent call last):'
        for frame in self.frames:
            if not frame.is_in_fw:
                yield u'  File "%s", line %s, in %s' % (
                    frame.filename,
                    frame.lineno,
                    frame.function_name
                )
                yield u'    ' + frame.current_line.strip()
        yield self.exception

    @property
    def full_tb(self):
        return u'\n'.join(self.generate_plaintext_traceback())

    @property
    def app_tb(self):
        return u'\n'.join(self.generate_plain_tb_app())


class Frame(object):
    """A single frame in a traceback."""

    def __init__(self, app, exc_type, exc_value, tb):
        self.app = app
        self.lineno = tb.tb_lineno
        self.function_name = tb.tb_frame.f_code.co_name
        self.locals = tb.tb_frame.f_locals
        self.globals = tb.tb_frame.f_globals

        fn = inspect.getsourcefile(tb) or inspect.getfile(tb)
        if fn[-4:] in ('.pyo', '.pyc'):
            fn = fn[:-1]
        # if it's a file on the file system resolve the real filename.
        if os.path.isfile(fn):
            fn = os.path.realpath(fn)
        self.filename = fn
        self.module = self.globals.get('__name__')
        #self.loader = self.globals.get('__loader__')
        self.code = tb.tb_frame.f_code

    @property
    def is_in_fw(self):
        fw_path = os.path.dirname(__file__)
        return self.filename[0:len(fw_path)] == fw_path

    @property
    def is_in_app(self):
        return self.filename[0:len(self.app.root_path)] == self.app.root_path

    @property
    def rendered_filename(self):
        if self.is_in_app:
            return self.filename[len(self.app.root_path)+1:]
        if self.is_in_fw:
            return "weppy."+self.filename[len(os.path.dirname(__file__))+1:]\
                .replace("/", ".").split(".py")[0]
        return self.filename

    @property
    def sourcelines(self):
        if not hasattr(self, '_sourcelines'):
            try:
                with open(self.filename, 'rb') as file:
                    source = file.read().decode('utf8')
            except IOError:
                source = '<unavailable>'
            self._sourcelines = source.splitlines()
        return self._sourcelines

    @property
    def sourceblock(self):
        lmax = self.lineno + 4
        return u'\n'.join(self.sourcelines[self.first_line_no-1:lmax])

    @property
    def first_line_no(self):
        l = self.lineno > 5 and (self.lineno - 5) or 1
        if l > len(self.sourcelines):
            l = 1
        while not self.sourcelines[l-1]:
            l += 1
            if l > len(self.sourcelines):
                break
        return l

    @property
    def current_line(self):
        try:
            return self.sourcelines[self.lineno - 1]
        except IndexError:
            return u''

    @property
    def render_locals(self):
        if not hasattr(self, '_rendered_locals'):
            self._rendered_locals = dict()
            for k, v in iteritems(self.locals):
                try:
                    self._rendered_locals[k] = str(v)
                except:
                    self._rendered_locals[k] = '<unavailable>'
        return self._rendered_locals


def make_traceback(exc_info, template_ref=None):
    if template_ref:
        if isinstance(exc_info[1], SyntaxError):
            if exc_info[1].filename == '<string>':
                exc_info = translate_syntax_error(exc_info[1], template_ref)
    if isinstance(exc_info[1], TemplateError):
        exc_info = translate_template_error(exc_info[1])
    tb = translate_exception(exc_info, 1)
    exc_type, exc_value, tb = tb.standard_exc_info
    reraise(exc_type, exc_value, tb)


def translate_syntax_error(error, reference):
    """Rewrites a syntax error to please traceback systems."""
    #error.translated = True
    #exc_info = (error.__class__, error, None)
    exc_info = (error.__class__, 'invalid syntax', None)
    filename = reference.file_path
    if filename is None:
        filename = '<unknown>'
    return fake_exc_info(exc_info, filename, reference.lineno)


def translate_template_error(error):
    exc_info = (error.__class__, error, None)
    filename = error.file_path
    if filename is None:
        filename = '<unknown>'
    return fake_exc_info(exc_info, filename, error.lineno)


def smart_traceback(app):
    exc_type, exc_value, tb = sys.exc_info()
    return Traceback(app, exc_type, exc_value, tb)


def debug_handler(tb):
    from os.path import join, dirname, basename
    view = join(dirname(__file__), 'assets', 'debug', basename('view.html'))
    from .templating.core import DummyResponse
    from .templating.parser import TemplateParser
    view_file = open(view, 'rb')
    view_source = view_file.read().decode('utf8')
    view_file.close()
    context = {'_DummyResponse_': DummyResponse(), 'tb': tb}
    from .datastructures import sdict
    t_dict = sdict(lexers={})
    code = str(TemplateParser(t_dict, view_source,
               context=context, path=''))
    exec(code, context)
    return context['_DummyResponse_'].body.getvalue()


def make_frame_proxy(frame):
    proxy = TracebackFrameProxy(frame)
    if tproxy is None:
        return proxy

    def operation_handler(operation, *args, **kwargs):
        if operation in ('__getattribute__', '__getattr__'):
            return getattr(proxy, args[0])
        elif operation == '__setattr__':
            proxy.__setattr__(*args, **kwargs)
        else:
            return getattr(proxy, operation)(*args, **kwargs)
    return tproxy(TracebackType, operation_handler)


def translate_exception(exc_info, initial_skip=0):
    """If passed an exc_info it will automatically rewrite the exceptions
    all the way down to the correct line numbers and frames.
    """
    tb = exc_info[2]
    frames = []

    # skip some internal frames if wanted
    for x in range(initial_skip):
        if tb is not None:
            tb = tb.tb_next

    while tb is not None:
        # save a reference to the next frame if we override the current
        # one with a faked one.
        next = tb.tb_next

        # fake template exceptions
        template = tb.tb_frame.f_globals.get('__weppy_template__')
        if template is not None:
            lineno = template.lineno
            tb = fake_exc_info(exc_info[:2] + (tb,), template.file_path,
                               lineno)[2]

        frames.append(make_frame_proxy(tb))
        tb = next

    # if we don't have any exceptions in the frames left, we have to
    # reraise it unchanged.
    # XXX: can we backup here?  when could this happen?
    if not frames:
        reraise(exc_info[0], exc_info[1], exc_info[2])

    return ProcessedTraceback(exc_info[0], exc_info[1], frames)


def fake_exc_info(exc_info, filename, lineno):
    """Helper for `translate_exception`."""
    exc_type, exc_value, tb = exc_info

    # figure the real context out
    if tb is not None:
        real_locals = tb.tb_frame.f_locals.copy()
        ctx = real_locals.get('context')
        if ctx:
            locals = ctx
        else:
            locals = {}
        #for name, value in iteritems(real_locals):
        #    if name.startswith('l_') and value is not missing:
        #        locals[name[2:]] = value

        # if there is a local called __weppy_exception__, we get
        # rid of it to not break the debug functionality.
        locals.pop('__weppy_exception__', None)
    else:
        locals = {}

    # assamble fake globals we need
    globals = {
        '__name__':             filename,
        '__file__':             filename,
        '__weppy_exception__':  exc_info[:2],

        # we don't want to keep the reference to the template around
        # to not cause circular dependencies, but we mark it as weppy
        # frame for the ProcessedTraceback
        '__weppy_template__':   None
    }

    # and fake the exception
    code = compile('\n' * (lineno - 1) + raise_helper, filename, 'exec')

    # if it's possible, change the name of the code.  This won't work
    # on some python environments such as google appengine
    try:
        code = CodeType(0, code.co_nlocals, code.co_stacksize,
                        code.co_flags, code.co_code, code.co_consts,
                        code.co_names, code.co_varnames, filename,
                        'template', code.co_firstlineno,
                        code.co_lnotab, (), ())
    except:
        pass

    # execute the code and catch the new traceback
    try:
        exec(code, globals, locals)
    except:
        exc_info = sys.exc_info()
        new_tb = exc_info[2].tb_next

    # return without this frame
    return exc_info[:2] + (new_tb,)


def _init_ugly_crap():
    """This function implements a few ugly things so that we can patch the
    traceback objects.  The function returned allows resetting `tb_next` on
    any python traceback object.  Do not attempt to use this on non cpython
    interpreters
    """
    import ctypes

    # figure out side of _Py_ssize_t
    if hasattr(ctypes.pythonapi, 'Py_InitModule4_64'):
        _Py_ssize_t = ctypes.c_int64
    else:
        _Py_ssize_t = ctypes.c_int

    # regular python
    class _PyObject(ctypes.Structure):
        pass
    _PyObject._fields_ = [
        ('ob_refcnt', _Py_ssize_t),
        ('ob_type', ctypes.POINTER(_PyObject))
    ]

    # python with trace
    if hasattr(sys, 'getobjects'):
        class _PyObject(ctypes.Structure):
            pass
        _PyObject._fields_ = [
            ('_ob_next', ctypes.POINTER(_PyObject)),
            ('_ob_prev', ctypes.POINTER(_PyObject)),
            ('ob_refcnt', _Py_ssize_t),
            ('ob_type', ctypes.POINTER(_PyObject))
        ]

    class _Traceback(_PyObject):
        pass
    _Traceback._fields_ = [
        ('tb_next', ctypes.POINTER(_Traceback)),
        ('tb_frame', ctypes.POINTER(_PyObject)),
        ('tb_lasti', ctypes.c_int),
        ('tb_lineno', ctypes.c_int)
    ]

    def tb_set_next(tb, next):
        """Set the tb_next attribute of a traceback object."""
        if not (isinstance(tb, TracebackType) and
                (next is None or isinstance(next, TracebackType))):
            raise TypeError('tb_set_next arguments must be traceback objects')
        obj = _Traceback.from_address(id(tb))
        if tb.tb_next is not None:
            old = _Traceback.from_address(id(tb.tb_next))
            old.ob_refcnt -= 1
        if next is None:
            obj.tb_next = ctypes.POINTER(_Traceback)()
        else:
            next = _Traceback.from_address(id(next))
            next.ob_refcnt += 1
            obj.tb_next = ctypes.pointer(next)

    return tb_set_next


# try to get a tb_set_next implementation if we don't have transparent
# proxies.
tb_set_next = None
if tproxy is None:
    try:
        tb_set_next = _init_ugly_crap()
    except:
        pass
    del _init_ugly_crap
