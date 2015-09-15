# -*- coding: utf-8 -*-
"""
    weppy.templating.contents
    -------------------------

    Provides structures for templating system.

    :copyright: (c) 2015 by Giovanni Barillari

    Based on the web2py's templating system (http://www.web2py.com)
    :copyright: (c) by Massimo Di Pierro <mdipierro@cs.depaul.edu>

    :license: BSD, see LICENSE for more details.
"""

from .._compat import implements_to_string, to_unicode


def _gen_output(node, blocks):
    if isinstance(node, BlockNode):
        if node.name in blocks:
            rv = blocks[node.name].output(blocks)
        else:
            rv = node.output(blocks)
    else:
        rv = to_unicode(node)
    return rv


@implements_to_string
class Node(object):
    """
    Basic Container Object
    """
    def __init__(self, value=None, pre_extend=False, template=None,
                 lines=None):
        self.value = value
        self.pre_extend = pre_extend
        self.template = template
        self.lines = lines or (None, None)

    def __str__(self):
        return to_unicode(self.value)

    def _rendered_lines(self):
        return str(self).split("\n")[1:]


@implements_to_string
class SuperNode(Node):
    def __init__(self, name='', pre_extend=False):
        self.name = name
        self.value = None
        self.pre_extend = pre_extend

    def __str__(self):
        if self.value:
            return to_unicode(self.value)
        else:
            return u''

    def __repr__(self):
        return "%s->%s" % (self.name, self.value)


@implements_to_string
class BlockNode(Node):
    """
    Block Container.

    This Node can contain other Nodes and will render in a hierarchical order
    of when nodes were added.

    ie::

        {{ block test }}
            This is default block test
        {{ end }}
    """
    def __init__(self, name='', pre_extend=False, delimiters=('{{', '}}')):
        """
        name - Name of this Node.
        """
        self.nodes = []
        self.name = name
        self.pre_extend = pre_extend
        self.left, self.right = delimiters

    def __repr__(self):
        lines = ['%sblock %s%s' % (self.left, self.name, self.right)]
        lines += [str(node) for node in self.nodes]
        lines.append('%send%s' % (self.left, self.right))
        return ''.join(lines)

    def __str__(self):
        """
        Get this BlockNodes content, not including child Nodes
        """
        return u''.join(str(node) for node in self.nodes
                        if not isinstance(node, BlockNode))

    def append(self, node):
        """
        Add an element to the nodes.

        Keyword Arguments

        - node -- Node object or string to append.
        """
        if isinstance(node, (str, Node)):
            self.nodes.append(node)
        else:
            raise TypeError("Invalid type; must be instance of ``str`` or " +
                            "``BlockNode``. %s" % node)

    def extend(self, other):
        """
        Extend the list of nodes with another BlockNode class.

        Keyword Arguments

        - other -- BlockNode or Content object to extend from.
        """
        if isinstance(other, BlockNode):
            self.nodes.extend(other.nodes)
        else:
            raise TypeError(
                "Invalid type; must be instance of ``BlockNode``. %s" % other)

    def output(self, blocks):
        """
        Merges all nodes into a single string.
        blocks -- Dictionary of blocks that are extending
        from this template.
        """
        return u''.join(_gen_output(node, blocks) for node in self.nodes)


@implements_to_string
class Content(BlockNode):
    """
    Parent Container -- Used as the root level BlockNode.

    Contains functions that operate as such.
    """
    def __init__(self, name="ContentBlock", pre_extend=False):
        """
        Keyword Arguments

        name -- Unique name for this BlockNode
        """
        self.name = name
        self.nodes = []
        self.blocks = {}
        self.pre_extend = pre_extend
        self.template = name

    def __str__(self):
        return u''.join(_gen_output(node, self.blocks) for node in self.nodes)

    def _insert(self, other, index=0):
        """
        Inserts object at index.
        """
        if isinstance(other, (str, Node)):
            self.nodes.insert(index, other)
        else:
            raise TypeError(
                "Invalid type, must be instance of ``str`` or ``Node``.")

    def insert(self, other, index=0):
        """
        Inserts object at index.

        You may pass a list of objects and have them inserted.
        """
        if isinstance(other, (list, tuple)):
            # Must reverse so the order stays the same.
            other.reverse()
            for item in other:
                self._insert(item, index)
        else:
            self._insert(other, index)

    def append(self, node):
        """
        Adds a node to list. If is a BlockNode then we assign a block for it.
        """
        if isinstance(node, (str, Node)):
            self.nodes.append(node)
            if isinstance(node, BlockNode):
                self.blocks[node.name] = node
        else:
            raise TypeError("Invalid type, must be instance of ``str`` or " +
                            "``BlockNode``. %s" % node)

    def extend(self, other):
        """
        Extends the objects list of nodes with another objects nodes
        """
        if isinstance(other, BlockNode):
            self.nodes.extend(other.nodes)
            self.blocks.update(other.blocks)
        else:
            raise TypeError(
                "Invalid type; must be instance of ``BlockNode``. %s" % other)

    def clear_content(self):
        self.nodes = []
