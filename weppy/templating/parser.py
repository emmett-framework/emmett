# -*- coding: utf-8 -*-
"""
    weppy.templating.parser
    -----------------------

    Provides the templating parser.

    :copyright: (c) 2014-2017 by Giovanni Barillari

    Based on the web2py's templating system (http://www.web2py.com)
    :copyright: (c) by Massimo Di Pierro <mdipierro@cs.depaul.edu>

    :license: BSD, see LICENSE for more details.
"""

from re import compile, sub, escape, DOTALL
from .._compat import implements_to_string, to_unicode
from .contents import Node, BlockNode, Content
from .helpers import TemplateError
from .lexers import default_lexers


@implements_to_string
class TemplateParser(object):
    default_delimiters = ('{{', '}}')
    r_tag = compile(r'(\{\{.*?\}\})', DOTALL)

    r_multiline = compile(r'(""".*?""")|(\'\'\'.*?\'\'\')', DOTALL)

    # These are used for re-indentation.
    # Indent + 1
    re_block = compile('^(elif |else:|except:|except |finally:).*$', DOTALL)

    # Indent - 1
    re_unblock = compile('^(return|continue|break|raise)( .*)?$', DOTALL)
    # Indent - 1
    re_pass = compile('^pass( .*)?$', DOTALL)

    def __init__(self, templater, text, name="ParserContainer", context={},
                 path='templates/', writer='_DummyResponse_.write', lexers={},
                 delimiters=('{{', '}}'), _super_nodes=[]):
        """
        text -- text to parse
        context -- context to parse in
        path -- folder path to templates
        writer -- string of writer class to use
        lexers -- dict of custom lexers to use.
        delimiters -- for example ('{{','}}')
        _super_nodes -- a list of nodes to check for inclusion
                        this should only be set by "self.extend"
                        It contains a list of SuperNodes from a child
                        template that need to be handled.
        """
        self.templater = templater
        # Keep a root level name.
        self.name = name
        # Raw text to start parsing.
        self.text = text
        # Writer to use (refer to the default for an example).
        # This will end up as
        # "%s(%s, escape=False)" % (self.writer, value)
        self.writer = writer

        # Dictionary of custom name lexers to use.
        #if isinstance(lexers, dict):
        #    self.lexers = lexers
        #else:
        #    self.lexers = {}
        self.lexers = default_lexers
        self.lexers.update(self.templater.lexers)

        # Path of templates
        self.path = path
        # Context for templates.
        self.context = context

        # allow optional alternative delimiters
        self.delimiters = delimiters
        if delimiters != self.default_delimiters:
            escaped_delimiters = (escape(delimiters[0]),
                                  escape(delimiters[1]))
            self.r_tag = compile(r'(%s.*?%s)' % escaped_delimiters, DOTALL)
        #elif hasattr(context.get('response', None), 'delimiters'):
        #    if context['response'].delimiters != self.default_delimiters:
        #        escaped_delimiters = (
        #            escape(context['response'].delimiters[0]),
        #            escape(context['response'].delimiters[1]))
        #        self.r_tag = compile(r'(%s.*?%s)' % escaped_delimiters,
        #                             DOTALL)

        # Create a root level Content that everything will go into.
        self.content = Content(name=name)

        # Stack will hold our current stack of nodes.
        # As we descend into a node, it will be added to the stack
        # And when we leave, it will be removed from the stack.
        # self.content should stay on the stack at all times.
        self.stack = [self.content]

        # This variable will hold a reference to every super block
        # that we come across in this template.
        self.super_nodes = []

        # This variable will hold a reference to the child
        # super nodes that need handling.
        self.child_super_nodes = _super_nodes

        # This variable will hold a reference to every block
        # that we come across in this template
        self.blocks = {}

        self.included_templates = []
        self.current_lines = (1, 1)

        # Begin parsing.
        self.parse(text)

    def create_block(self, name=None, pre_extend=False, delimiters=None):
        return BlockNode(name=name, pre_extend=pre_extend,
                         delimiters=delimiters or self.delimiters)

    def create_node(self, value, pre_extend=False, use_writer=True,
                    writer_escape=True):
        if use_writer:
            if not writer_escape:
                value = u"\n%s(%s, escape=False)" % (self.writer, value)
            else:
                value = u"\n%s(%s)" % (self.writer, value)
        else:
            value = u"\n%s" % value
        return Node(value, pre_extend=pre_extend, template=self.name,
                    lines=self.current_lines)

    def create_htmlnode(self, value, pre_extend=False):
        value = u"\n%s(%r, escape=False)" % (self.writer, value)
        return Node(value, pre_extend=pre_extend, template=self.name,
                    lines=self.current_lines)

    def __str__(self):
        return self.reindent(to_unicode(self.content))

    def reindent(self, text):
        """
        Reindents a string of unindented python code.
        """

        # Get each of our lines into an array.
        lines = text.split('\n')

        # Our new lines
        new_lines = []

        # Keeps track of how many indents we have.
        # Used for when we need to drop a level of indentation
        # only to reindent on the next line.
        credit = 0

        # Current indentation
        k = 0

        #################
        # THINGS TO KNOW
        #################

        # k += 1 means indent
        # k -= 1 means unindent
        # credit = 1 means unindent on the next line.

        for raw_line in lines:
            line = raw_line.strip()

            # ignore empty lines
            if not line:
                continue

            # If we have a line that contains python code that
            # should be unindented for this line of code.
            # and then reindented for the next line.
            if TemplateParser.re_block.match(line):
                k = k + credit - 1

            # We obviously can't have a negative indentation
            k = max(k, 0)

            # Add the indentation!
            new_lines.append(u' ' * (4 * k) + line)

            # Bank account back to 0 again :(
            credit = 0

            # If we are a pass block, we obviously de-dent.
            if TemplateParser.re_pass.match(line):
                k -= 1

            # If we are any of the following, de-dent.
            # However, we should stay on the same level
            # But the line right after us will be de-dented.
            # So we add one credit to keep us at the level
            # while moving back one indentation level.
            if TemplateParser.re_unblock.match(line):
                credit = 1
                k -= 1

            # If we are an if statement, a try, or a semi-colon we
            # probably need to indent the next line.
            if line.endswith(':') and not line.startswith('#'):
                k += 1

        # This must come before so that we can raise an error with the
        # right content.
        new_text = u'\n'.join(new_lines)

        if k > 0:
            #self._raise_error('missing "pass" in view', new_text)
            raise TemplateError(self.path, 'missing "pass" in view',
                                self.name, 1)
        elif k < 0:
            #self._raise_error('too many "pass" in view', new_text)
            raise TemplateError(self.path, 'too many "pass" in view',
                                self.name, 1)

        return new_text

    def _get_file_text(self, filename):
        """
        Attempt to open ``filename`` and retrieve its text.

        This will use self.path to search for the file.
        """

        # If they didn't specify a filename, how can we find one!
        if not filename.strip():
            #self._raise_error('Invalid template filename')
            raise TemplateError(self.path, 'Invalid template filename',
                                self.name, 1)

        # Allow Views to include other views dynamically
        context = self.context
        #if current and not "response" in context:
        #    context["response"] = getattr(current, 'response', None)

        # Get the filename; filename looks like ``"template.html"``.
        # We need to eval to remove the quotes and get the string type.
        filename = eval(filename, context)

        # Get the path of the file on the system.
        #filepath = self.path and os.path.join(self.path, filename) or filename

        # Get the file and read the content
        tpath, tname = self.templater.preload(
            self.path, filename)
        try:
            tsource = self.templater.load(tpath, tname)
        except:
            raise TemplateError(self.path, 'Unable to open included view file',
                                self.name, 1)
        tsource = self.templater.prerender(tsource, tname)

        self.included_templates.append((tpath, tname, tsource))

        return tsource, tname

    def include(self, content, filename):
        """
        Include ``filename`` here.
        """
        text, tname = self._get_file_text(filename)

        t = TemplateParser(self.templater, text,
                           name=tname,
                           context=self.context,
                           path=self.path,
                           writer=self.writer,
                           delimiters=self.delimiters)

        content.append(t.content)

    def extend(self, filename):
        """
        Extend ``filename``. Anything not declared in a block defined by the
        parent will be placed in the parent templates ``{{include}}`` block.
        """
        text, tname = self._get_file_text(filename)

        # Create out nodes list to send to the parent
        super_nodes = []
        # We want to include any non-handled nodes.
        super_nodes.extend(self.child_super_nodes)
        # And our nodes as well.
        super_nodes.extend(self.super_nodes)

        t = TemplateParser(self.templater, text,
                           name=tname,
                           context=self.context,
                           path=self.path,
                           writer=self.writer,
                           delimiters=self.delimiters,
                           _super_nodes=super_nodes)

        # Make a temporary buffer that is unique for parent
        # template.
        buf = BlockNode(
            name='__include__' + tname, delimiters=self.delimiters)
        pre = []

        # Iterate through each of our nodes
        for node in self.content.nodes:
            # If a node is a block
            if isinstance(node, BlockNode):
                # That happens to be in the parent template
                if node.name in t.content.blocks:
                    # Do not include it
                    continue

            if isinstance(node, Node):
                # Or if the node was before the extension
                # we should not include it
                if node.pre_extend:
                    pre.append(node)
                    continue

            # Otherwise, it should go int the
            # Parent templates {{include}} section.
                buf.append(node)
            else:
                buf.append(node)

        # Clear our current nodes. We will be replacing this with
        # the parent nodes.
        self.content.nodes = []

        t_content = t.content

        # Set our include, unique by filename
        t_content.blocks['__include__' + tname] = buf

        # Make sure our pre_extended nodes go first
        t_content.insert(pre)

        # Then we extend our blocks
        t_content.extend(self.content)

        # Work off the parent node.
        self.content = t_content

    def parse(self, text):
        # Basically, r_tag.split will split the text into
        # an array containing, 'non-tag', 'tag', 'non-tag', 'tag'
        # so if we alternate this variable, we know
        # what to look for. This is alternate to
        # line.startswith("{{")
        self._in_tag = False
        self._needs_extend = None
        self._is_pre_extend = True
        last_was_code_block = False

        # Use a list to store everything in
        # This is because later the code will "look ahead"
        # for missing strings or brackets.
        ij = self.r_tag.split(text)
        # j = current index
        # i = current item

        stack = self.stack
        for j in range(len(ij)):
            i = ij[j]

            if i:
                self.current_lines = (self.current_lines[1],
                                      self.current_lines[1] +
                                      len(i.split("\n")) - 1)

                if not stack:
                    raise TemplateError(
                        self.path, 'The "end" tag is unmatched, please check' +
                        ' if you have a starting "block" tag', self.name,
                        self.current_lines)

                # Our current element in the stack.
                top = stack[-1]

                if self._in_tag:
                    line = i

                    # Get rid of '{{' and '}}'
                    line = line[2:-2].strip()

                    # This is bad juju, but let's do it anyway
                    if not line:
                        continue

                    # We do not want to replace the newlines in code,
                    # only in block comments.
                    def remove_newline(re_val):
                        # Take the entire match and replace newlines with
                        # escaped newlines.
                        return re_val.group(0).replace('\n', '\\n')

                    # Perform block comment escaping.
                    # This performs escaping ON anything
                    # in between """ and """
                    line = sub(TemplateParser.r_multiline,
                               remove_newline,
                               line)

                    if line.startswith('='):
                        # IE: {{=response.title}}
                        name, value = '=', line[1:].strip()
                    else:
                        v = line.split(' ', 1)
                        if len(v) == 1:
                            # Example
                            # {{ include }}
                            # {{ end }}
                            name = v[0]
                            value = u''
                        else:
                            # Example
                            # {{ block pie }}
                            # {{ include "layout.html" }}
                            # {{ for i in range(10): }}
                            name = v[0]
                            value = v[1]

                    # This will replace newlines in block comments
                    # with the newline character. This is so that they
                    # retain their formatting, but squish down to one
                    # line in the rendered template.

                    # Check presence of an appropriate lexer
                    lexer = self.lexers.get(name)
                    if lexer and not value.startswith('='):
                        lexer(parser=self, value=value)
                        last_was_code_block = False
                    else:
                        # If we don't know where it belongs
                        # we just add it anyways without formatting.
                        if line and self._in_tag:

                            # Split on the newlines >.<
                            tokens = line.split('\n')

                            # We need to look for any instances of
                            # for i in range(10):
                            #   = i
                            # pass
                            # So we can properly put a writer in place.
                            continuation = False
                            len_parsed = 0
                            for k, token in enumerate(tokens):

                                token = tokens[k] = token.strip()
                                len_parsed += len(token)

                                if token.startswith('='):
                                    if token.endswith('\\'):
                                        continuation = True
                                        tokens[k] = u"%s(%s" % (
                                            self.writer, token[1:].strip())
                                    else:
                                        tokens[k] = u"%s(%s)" % (
                                            self.writer, token[1:].strip())
                                elif continuation:
                                    tokens[k] += u')'
                                    continuation = False

                            buf = u'\n'.join(tokens)
                            node = self.create_node(buf, self._is_pre_extend,
                                                    use_writer=False)
                            top.append(node)
                            last_was_code_block = True

                else:
                    if not last_was_code_block or (
                            last_was_code_block and i.strip()):
                        # It is HTML so just include it.
                        node = self.create_htmlnode(i, self._is_pre_extend)
                        top.append(node)
                    last_was_code_block = False

            # Remember: tag, not tag, tag, not tag
            self._in_tag = not self._in_tag

        # Make a list of items to remove from child
        to_rm = []

        # Go through each of the children nodes
        for node in self.child_super_nodes:
            # If we declared a block that this node wants to include
            if node.name in self.blocks:
                # Go ahead and include it!
                node.value = self.blocks[node.name]
                # Since we processed this child, we don't need to
                # pass it along to the parent
                to_rm.append(node)

        # Remove some of the processed nodes
        for node in to_rm:
            # Since this is a pointer, it works beautifully.
            # Sometimes I miss C-Style pointers... I want my asterisk...
            self.child_super_nodes.remove(node)

        # If we need to extend a template.
        if self._needs_extend:
            self.extend(self._needs_extend)
