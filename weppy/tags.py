# -*- coding: utf-8 -*-
"""
    weppy.tags
    ----------

    Provides html generation classes.

    :copyright: (c) 2015 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

import re
import threading

from .libs.sanitizer import sanitize

__all__ = ['tag', 'cat', 'safe', 'asis']

THREAD_LOCAL = threading.local()


def xmlescape(s, quote=True):
    """
    returns an escaped string of the provided text s
    s: the text to be escaped
    quote: optional (default True)
    """
    # first try the xml function
    if isinstance(s, TAG):
        return s.xml()
    # otherwise, make it a string
    if not isinstance(s, (str, unicode)):
        s = str(s)
    elif isinstance(s, unicode):
        s = s.encode('utf8', 'xmlcharrefreplace')
    s = s.replace("&", "&amp;")  # Must be done first!
    s = s.replace("<", "&lt;")
    s = s.replace(">", "&gt;")
    if quote:
        s = s.replace("'", "&#x27;")
        s = s.replace('"', "&quot;")
    return s


class TAG(object):
    rules = {'ul': ['li'],
             'ol': ['li'],
             'table': ['tr', 'thead', 'tbody'],
             'thead': ['tr'],
             'tbody': ['tr'],
             'tr': ['td', 'th'],
             'select': ['option', 'optgroup'],
             'optgroup': ['optionp']}
    _self_closed = ['br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta']

    def __init__(self, name):
        self.safe = safe
        self.name = name
        self.parent = None
        self.components = []
        self.attributes = {}
        if hasattr(THREAD_LOCAL, "stack") and THREAD_LOCAL.stack:
            THREAD_LOCAL.stack[-1].append(self)

    def __enter__(self):
        if not hasattr(THREAD_LOCAL, "stack"):
            THREAD_LOCAL.stack = []
        THREAD_LOCAL.stack.append(self)
        return self

    def __exit__(self, type, value, traceback):
        THREAD_LOCAL.stack.pop(-1)

    @staticmethod
    def wrap(component, rules):
        if rules and (not isinstance(component, TAG) or
                      component.name not in rules):
            return TAG(rules[0])(component)
        return component

    def __call__(self, *components, **attributes):
        rules = self.rules.get(self.name, [])
        self.components = [self.wrap(comp, rules) for comp in components]
        self.attributes = attributes
        for component in self.components:
            if isinstance(component, TAG):
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
        return self.xml()

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
            tags = reduce(union, [self.find(x.strip())
                                  for x in expr.split(',')], set())
        elif ' ' in expr:
            tags = [self]
            for k, item in enumerate(expr.split()):
                if k > 0:
                    children = [set([c for c in tag if isinstance(c, TAG)])
                                for tag in tags]
                    tags = reduce(union, children)
                tags = reduce(union, [tag.find(item) for tag in tags], set())
        else:
            tags = reduce(union, [c.find(expr)
                                  for c in self if isinstance(c, TAG)], set())
            tag = TAG.regex_tag.match(expr)
            id = TAG.regex_id.match(expr)
            _class = TAG.regex_class.match(expr)
            attr = TAG.regex_attr.match(expr)
            if (tag is None or self.name == tag.group(1)) and \
               (id is None or self['_id'] == id.group(1)) and \
               (_class is None or _class.group(1) in
                    (self['_class'] or '').split()) and \
               (attr is None or self['_'+attr.group(1)] == attr.group(2)):
                tags.add(self)
        return tags

    def xml(self):
        name = self.name
        ca = ' '.join(
            '%s="%s"' % (k[1:], k[1:] if v == True else xmlescape(v))
            for (k, v) in sorted(self.attributes.items())
            if k.startswith('_') and v is not None)
        da = self.attributes.get('data', {})
        ca_data = ' '.join(
            'data-%s="%s"' % (k, xmlescape(v)) for k, v in da.iteritems())
        if ca_data:
            ca = ca + ' ' + ca_data
        ca = ' ' + ca if ca else ''
        if name in self._self_closed:
            return '<%s%s />' % (name, ca)
        else:
            co = ''.join(xmlescape(v) for v in self.components)
            return '<%s%s>%s</%s>' % (name, ca, co, name)

    __repr__ = __str__


class METATAG(object):
    def __getattr__(self, name):
        return TAG(name)

    def __getitem__(self, name):
        return TAG(name)

tag = METATAG()


class cat(TAG):
    def __init__(self, *components):
        self.components = [c for c in components]
        self.attributes = {}

    def xml(self):
        return ''.join(xmlescape(v) for v in self.components)


class safe(TAG):
    default_allowed_tags = {
        'a': ['href', 'title', 'target'], 'b': [], 'blockquote': ['type'],
        'br': [], 'i': [], 'li': [], 'ol': [], 'ul': [], 'p': [], 'cite': [],
        'code': [], 'pre': [], 'img': ['src', 'alt'], 'strong': [],
        'h1': [], 'h2': [], 'h3': [], 'h4': [], 'h5': [], 'h6': [],
        'table': [], 'tr': [], 'td': ['colspan'], 'div': [],
        }

    def __init__(self, text, sanitize=False, allowed_tags=None):
        self.text = text
        self.sanitize = sanitize
        self.allowed_tags = allowed_tags or safe.default_allowed_tags

    def xml(self):
        if self.sanitize:
            return sanitize(self.text, self.allowed_tags.keys(),
                            self.allowed_tags)
        if not isinstance(self.text, basestring):
            return str(self.text)
        return self.text


def asis(text):
    return safe(text)
