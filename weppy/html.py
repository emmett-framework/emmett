# -*- coding: utf-8 -*-
"""
    weppy.html
    ----------

    Provides html generation classes.

    :copyright: (c) 2014-2017 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

import cgi
import re
import threading
from ._compat import (
    iteritems, text_type, implements_to_string, implements_bool, to_unicode,
    to_native)
from .libs.sanitizer import sanitize

__all__ = ['tag', 'cat', 'safe', 'asis']


@implements_bool
class TagStack(threading.local):
    def __init__(self):
        self.stack = []

    def __getitem__(self, key):
        return self.stack[key]

    def append(self, item):
        self.stack.append(item)

    def pop(self, idx):
        self.stack.pop(idx)

    def __bool__(self):
        return len(self.stack) > 0


_stack = TagStack()


def _to_unicode(obj):
    if not isinstance(obj, text_type):
        return to_unicode(obj)
    return obj


#: cgi module seems faster
# def htmlescape(obj):
#     if hasattr(obj, '__html__'):
#         return obj.__html__()
#     return (
#         _to_unicode(obj)
#         .replace('&', '&amp;')
#         .replace('>', '&gt;')
#         .replace('<', '&lt;')
#         .replace("'", '&#39;')
#         .replace('"', '&#34;')
#     )


def htmlescape(obj):
    if hasattr(obj, '__html__'):
        return obj.__html__()
    return cgi.escape(_to_unicode(obj), True).replace(u"'", u"&#39;")


@implements_to_string
class HtmlTag(object):
    rules = {
        'ul': ['li'],
        'ol': ['li'],
        'table': ['tr', 'thead', 'tbody'],
        'thead': ['tr'],
        'tbody': ['tr'],
        'tr': ['td', 'th'],
        'select': ['option', 'optgroup'],
        'optgroup': ['optionp']}
    _self_closed = {'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta'}

    def __init__(self, name):
        self.safe = safe
        self.name = name
        self.parent = None
        self.components = []
        self.attributes = {}
        if _stack:
            _stack[-1].append(self)

    def __enter__(self):
        _stack.append(self)
        return self

    def __exit__(self, type, value, traceback):
        _stack.pop(-1)

    @staticmethod
    def wrap(component, rules):
        if rules and (
            not isinstance(component, HtmlTag) or component.name not in rules
        ):
            return HtmlTag(rules[0])(component)
        return component

    def __call__(self, *components, **attributes):
        rules = self.rules.get(self.name, [])
        self.components = [self.wrap(comp, rules) for comp in components]
        self.attributes = attributes
        for component in self.components:
            if isinstance(component, HtmlTag):
                component.parent = self
        return self

    def append(self, component):
        self.components.append(component)

    def insert(self, i, component):
        self.components.insert(i, component)

    def remove(self, component):
        self.components.remove(component)

    def __getitem__(self, key):
        if isinstance(key, int):
            return self.components[key]
        else:
            return self.attributes.get(key)

    def __setitem__(self, key, value):
        if isinstance(key, int):
            self.components.insert(key, value)
        else:
            self.attributes[key] = value

    def __iter__(self):
        for item in self.components:
            yield item

    def __str__(self):
        return self.__html__()

    def __add__(self, other):
        return cat(self, other)

    def add_class(self, name):
        """ add a class to _class attribute """
        c = self['_class']
        classes = (set(c.split()) if c else set()) | set(name.split())
        self['_class'] = ' '.join(classes) if classes else None
        return self

    def remove_class(self, name):
        """ remove a class from _class attribute """
        c = self['_class']
        classes = (set(c.split()) if c else set()) - set(name.split())
        self['_class'] = ' '.join(classes) if classes else None
        return self

    regex_tag = re.compile('^([\w\-\:]+)')
    regex_id = re.compile('#([\w\-]+)')
    regex_class = re.compile('\.([\w\-]+)')
    regex_attr = re.compile('\[([\w\-\:]+)=(.*?)\]')

    def find(self, expr):
        union = lambda a, b: a.union(b)
        if ',' in expr:
            tags = reduce(
                union,
                [self.find(x.strip()) for x in expr.split(',')],
                set())
        elif ' ' in expr:
            tags = [self]
            for k, item in enumerate(expr.split()):
                if k > 0:
                    children = [
                        set([c for c in tag if isinstance(c, HtmlTag)])
                        for tag in tags]
                    tags = reduce(union, children)
                tags = reduce(union, [tag.find(item) for tag in tags], set())
        else:
            tags = reduce(
                union,
                [c.find(expr) for c in self if isinstance(c, HtmlTag)],
                set())
            tag = HtmlTag.regex_tag.match(expr)
            id = HtmlTag.regex_id.match(expr)
            _class = HtmlTag.regex_class.match(expr)
            attr = HtmlTag.regex_attr.match(expr)
            if (
                (tag is None or self.name == tag.group(1)) and
                (id is None or self['_id'] == id.group(1)) and
                (_class is None or _class.group(1) in
                    (self['_class'] or '').split()) and
                (attr is None or self['_' + attr.group(1)] == attr.group(2))
            ):
                tags.add(self)
        return tags

    def _build_html_attributes(self):
        return u' '.join(
            u'%s="%s"' % (k[1:], k[1:] if v is True else htmlescape(v))
            for (k, v) in sorted(self.attributes.items())
            if k.startswith('_') and v is not None)

    def __html__(self):
        name = self.name
        attrs = self._build_html_attributes()
        data = self.attributes.get('data', {})
        data_attrs = u' '.join(
            u'data-%s="%s"' % (k, htmlescape(v)) for k, v in iteritems(data))
        if data_attrs:
            attrs = attrs + u' ' + data_attrs
        attrs = u' ' + attrs if attrs else u''
        if name in self._self_closed:
            return u'<%s%s />' % (name, attrs)
        components = u''.join(htmlescape(v) for v in self.components)
        return u'<%s%s>%s</%s>' % (name, attrs, components, name)

    def __json__(self):
        return str(self)


class MetaHtmlTag(object):
    def __getattr__(self, name):
        return HtmlTag(name)

    def __getitem__(self, name):
        return HtmlTag(name)


class cat(HtmlTag):
    def __init__(self, *components):
        self.components = [c for c in components]
        self.attributes = {}

    def __html__(self):
        return u''.join(htmlescape(v) for v in self.components)


class asis(HtmlTag):
    def __init__(self, text):
        self.text = text

    def __html__(self):
        return _to_unicode(self.text)


class safe(asis):
    default_allowed_tags = {
        'a': ['href', 'title', 'target'], 'b': [], 'blockquote': ['type'],
        'br': [], 'i': [], 'li': [], 'ol': [], 'ul': [], 'p': [], 'cite': [],
        'code': [], 'pre': [], 'img': ['src', 'alt'], 'strong': [],
        'h1': [], 'h2': [], 'h3': [], 'h4': [], 'h5': [], 'h6': [],
        'table': [], 'tr': [], 'td': ['colspan'], 'div': [],
    }

    def __init__(self, text, sanitize=False, allowed_tags=None):
        super(safe, self).__init__(text)
        self.sanitize = sanitize
        self.allowed_tags = allowed_tags or safe.default_allowed_tags

    def __html__(self):
        if self.sanitize:
            return sanitize(
                to_native(self.text),
                self.allowed_tags.keys(),
                self.allowed_tags)
        return super(safe, self).__html__()


tag = MetaHtmlTag()
