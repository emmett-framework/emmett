# -*- coding: utf-8 -*-
"""
emmett.html
-----------

Provides html generation classes.

:copyright: 2014 Giovanni Barillari
:license: BSD-3-Clause
"""

import re
from functools import reduce

from emmett_core.html import (
    MetaHtmlTag as _MetaHtmlTag,
    TagStack,
    TreeHtmlTag,
    _to_str,
    cat as cat,
    htmlescape as htmlescape,
)


__all__ = ["tag", "cat", "asis"]

_re_tag = re.compile(r"^([\w\-\:]+)")
_re_id = re.compile(r"#([\w\-]+)")
_re_class = re.compile(r"\.([\w\-]+)")
_re_attr = re.compile(r"\[([\w\-\:]+)=(.*?)\]")


class HtmlTag(TreeHtmlTag):
    __slots__ = []

    def __call__(self, *components, **attributes):
        # legacy "data" attribute
        if _data := attributes.pop("data", None):
            attributes["_data"] = _data
        return super().__call__(*components, **attributes)

    def find(self, expr):
        union = lambda a, b: a.union(b)
        if "," in expr:
            tags = reduce(union, [self.find(x.strip()) for x in expr.split(",")], set())
        elif " " in expr:
            tags = [self]
            for k, item in enumerate(expr.split()):
                if k > 0:
                    children = [{c for c in tag if isinstance(c, self.__class__)} for tag in tags]
                    tags = reduce(union, children)
                tags = reduce(union, [tag.find(item) for tag in tags], set())
        else:
            tags = reduce(union, [c.find(expr) for c in self if isinstance(c, self.__class__)], set())
            tag = _re_tag.match(expr)
            id = _re_id.match(expr)
            _class = _re_class.match(expr)
            attr = _re_attr.match(expr)
            if (
                (tag is None or self.name == tag.group(1))
                and (id is None or self["_id"] == id.group(1))
                and (_class is None or _class.group(1) in (self["_class"] or "").split())
                and (attr is None or self["_" + attr.group(1)] == attr.group(2))
            ):
                tags.add(self)
        return tags


class MetaHtmlTag(_MetaHtmlTag):
    __slots__ = []
    _tag_cls = HtmlTag


class asis(HtmlTag):
    __slots__ = []

    def __init__(self, val):
        self.name = val

    def __html__(self):
        return _to_str(self.name)


tag = MetaHtmlTag(TagStack())
