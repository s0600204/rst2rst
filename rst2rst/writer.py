"""reStructuredText document tree Writer."""

__docformat__ = 'reStructuredText'

import textwrap

import docutils
from docutils import frontend, nodes, utils, writers, languages, io
from docutils.parsers.rst.states import Inliner
from docutils.transforms import writer_aux
from docutils.utils.error_reporting import SafeString
from docutils.utils.math import unichar2tex, pick_math_environment
from docutils.utils.math.latex2mathml import parse_latex_math
from docutils.utils.math.math2html import math2html


class Options(object):
    """Options for rst to rst conversion."""
    def __init__(self):
        self.title_chars = [u'#', u'*', u'=', u'-', u'^', u'"']
        """List of symbols used to underline and overline titles.

        List indices are "heading level - 1", i.e. at index 0 is the symbol
        used to underline/overline "H1".

        """

        self.title_prefix = [u'', u'\n', u'', u'', u'', u'']
        """List of prefixes before title and overline (typically, blank lines).

        Indices represent heading level.

        """

        self.title_suffix = [u'\n'] * 6
        """List of suffixes after title and underline (typically, blank lines).

        Indices represent heading level.

        """

        self.title_overline = [True, True, False, False, False, False]
        """List of booleans specifying whether to overline the title or not.

        List indices represent heading level.

        """

        self.indentation_char = u' '
        """Character used for indentation.

        Should be space or tab. Default is space.

        """

        self.blockquote_indent = 2
        """Indentation level for blockquotes."""

        self.wrap_length = 79
        """Wrap length, i.e. maximum text width, as number of chararcters."""

        self.bullet_character = ['*'] * 6
        """List of symbols used for bullet lists."""


class Writer(writers.Writer):
    supported = ('txt')  # Formats this writer supports.
    config_section = 'rst writer'
    config_section_dependencies = ('writers',)

    def __init__(self):
        writers.Writer.__init__(self)
        self.translator_class = RSTTranslator
        self.options = Options()

    def translate(self):
        self.visitor = self.translator_class(self.document, self.options)
        self.document.walkabout(self.visitor)
        self.output = self.visitor.astext()


class RSTTranslator(nodes.NodeVisitor):
    """RST writer."""

    optional = (
        'document',
    )

    def __init__(self, document, options):
        self.options = options
        nodes.NodeVisitor.__init__(self, document)

        # Document parts.
        self.header = []
        self.title = []
        self.subtitle = []
        self.roles = []
        self.body = []
        self.footer = []

        # Context helpers.
        self.section_level = 0
        """Current section/title level, starting at 0.

        Section level is incremented/decremented during :py:meth:`visit_title`
        and :py:meth:`depart_title`.

        """

        self._indentation_levels = [0]
        """Stack of current indentation level.

        See also :py:attr:`indentation_level`, :py:meth:`indent` and
        :py:meth:`dedent`.

        """

        self._indent_first_line = [u'']

        self.spacer = ''
        """Buffer (string) that is to be inserted between two elements.

        The spacer isn't always inserted. As an example, it is not inserted at
        the end of the document.

        The spacer is typically assigned on depart_*() and inserted on next
        element's visit_*().

        """

        self.list_level = 0
        """Current level in nested lists."""

        self.buffer = []
        self.last_buffer_length = 0

        self.custom_roles = []

    # Dynamic properties

    @property
    def buffer_length(self):
        return len(''.join(self.buffer))

    @property
    def bullet_character(self):
        return self.options.bullet_character[self.list_level]

    @property
    def indentation(self):
        """Return current indentation as unicode."""
        return self.options.indentation_char * sum(self._indentation_levels)

    @property
    def indentation_level(self):
        """Return current indentation level."""
        return self._indentation_levels[-1]

    @property
    def initial_indentation(self):
        """Return current first-line indentation as unicode."""
        if self._indent_first_line[-1] is None:
            return self.indentation
        else:
            return self._indent_first_line[-1]

    # Helper methods

    def astext(self):
        content = self.header + self.title + self.subtitle + self.roles + self.body \
            + self.footer
        return ''.join(content)

    def dedent(self):
        """Decrease indentation by ``levels`` levels."""
        self._indent_first_line.pop()
        return self._indentation_levels.pop()

    def indent(self, levels, first_line=None):
        """Increase indentation by ``levels`` levels."""
        self._indentation_levels.append(levels)
        self._indent_first_line.append(first_line)

    def register_role(self, role):
        if role in self.custom_roles:
            return
        self.custom_roles.append(role)

        text = '.. role:: %s\n' % role
        self.roles.append(text)

    def render_buffer(self):
        """Append wrapped buffer to body."""
        self.body.append(self.spacer)
        text = ''.join(self.buffer)
        self.last_buffer_length = len(text)
        text = self.wrap(text) + '\n'
        self.body.append(text)
        self.buffer = []

    def render_title_line(self, section_level, length):
        symbol = self.options.title_chars[section_level]
        self.body.append(symbol * length)
        self.body.append('\n')

    def wrap(self, text, width=None, indent=None):
        """Return ``text`` wrapped to ``width`` and indented with ``indent``.

        By default:

        * ``width`` is ``self.options.wrap_length``
        * ``indent`` is ``self.indentation``.

        """
        width = width if width is not None else self.options.wrap_length
        indent = indent if indent is not None else self.indentation
        initial_indent = self.initial_indentation
        return textwrap.fill(text, width=width,
                             initial_indent=initial_indent,
                             subsequent_indent=indent)

    def write_to_buffer(self, text):
        """Delay rendering."""
        self.buffer.append(text)

    # {visit|depart}_* methods

    def visit_Text(self, node):
        text = node.astext().replace('*', r'\*')
        self.write_to_buffer(text)

    def depart_Text(self, node):
        pass

    def visit_abbreviation(self, node):
        self.write_to_buffer(':abbreviation:`')

    def depart_abbreviation(self, node):
        self.write_to_buffer('`')

    def visit_acronym(self, node):
        self.write_to_buffer(':acronym:`')

    def depart_acronym(self, node):
        self.write_to_buffer('`')

    def visit_block_quote(self, node):
        self.indent(self.options.blockquote_indent)

    def depart_block_quote(self, node):
        self.dedent()

    def visit_bullet_list(self, node):
        self.body.append(self.spacer)
        self.list_level += 1
        self.spacer = ''

    def depart_bullet_list(self, node):
        self.spacer = '\n'
        self.list_level -= 1

    def visit_classifier(self, node):
        self.write_to_buffer(' : ')

    def depart_classifier(self, node):
        pass

    def visit_definition(self, node):
        self.render_buffer()
        self.spacer = ''
        self.indent(2)

    def depart_definition(self, node):
        self.dedent()

    def visit_definition_list(self, node):
        self.list_level += 1
        self.spacer = '\n'

    def depart_definition_list(self, node):
        self.list_level -= 1

    def visit_definition_list_item(self, node):
        pass

    def depart_definition_list_item(self, node):
        pass

    def depart_document(self, node):
        if self.custom_roles:
            self.roles.append('\n')

    def visit_emphasis(self, node):
        self.write_to_buffer('*')

    def depart_emphasis(self, node):
        self.write_to_buffer('*')

    def visit_inline(self, node):
        classes = node.get('classes', [])
        for role in classes:
            self.register_role(role)
        classes = ' '.join(classes)
        self.write_to_buffer(':%s:`' % classes)

    def depart_inline(self, node):
        self.write_to_buffer('`')

    def visit_list_item(self, node):
        self.body.append(self.spacer)
        self.indent(2, '%s%s ' % (self.indentation, self.bullet_character))
        self.spacer = ''

    def depart_list_item(self, node):
        self.dedent()
        # Only space out list-items if the text in their final paragraph is
        # longer than the wrap length.
        #
        # Note: this will result in
        # > * Short line.
        # > * Loooonnnnnng line that wraps
        # >   onto a second line.
        # >
        # > * Short line.
        # which doesn't look very good IMO.
        #
        # @todo: Work out a way of doing this for *all* items if one item in the
        #        list is too long.
        if self.last_buffer_length > self.options.wrap_length:
            self.spacer = '\n'
        else:
            self.spacer = ''

    def visit_literal(self, node):
        self.write_to_buffer('``')

    def depart_literal(self, node):
        self.write_to_buffer('``')

    def visit_literal_block(self, node):
        # @todo: Support parsed-literal blocks
        # @todo: Support option "number-lines" and strip line numbers from the text
        classes = node.get('classes', [])
        if classes:
            self.write_to_buffer('.. code:: %s' % classes[1])
        else:
            if self.body[-1][-2] == ':':
                self.body[-1] = self.body[-1][:-2] + ':' + self.body[-1][-2:]
                self.spacer = ''
            else:
                self.write_to_buffer('::')

        self.render_buffer()
        self.body.append(self.spacer)
        self.spacer = '\n'

        self.indent(2)
        for line in node.astext().split('\n'):
            self.body.append('%s%s\n' % (self.indentation, line))
        self.dedent()
        raise nodes.SkipNode

    def visit_math(self, node):
        self.write_to_buffer(':math:`')

    def depart_math(self, node):
        self.write_to_buffer('`')

    def visit_paragraph(self, node):
        pass

    def depart_paragraph(self, node):
        self.render_buffer()
        self.spacer = '\n'
        self._indent_first_line[-1] = None

    def visit_reference(self, node):
        refuri = node.get('refuri')

        pep_uri = self.document.settings.pep_base_url
        if refuri.startswith(pep_uri):
            pep_template = self.document.settings.pep_file_url_template
            pep_num = refuri[len(pep_uri) + pep_template.index('%'):]
            self.write_to_buffer(':pep-reference:`%s`' % pep_num)
            raise nodes.SkipNode

        rfc_uri = self.document.settings.rfc_base_url
        if refuri.startswith(rfc_uri):
            rfc_template = Inliner.rfc_url
            rfc_num = refuri[
                len(rfc_uri) + rfc_template.index('%'):
                -(len(rfc_template) - rfc_template.index('.'))
            ]
            self.write_to_buffer(':rfc-reference:`%s`' % rfc_num)
            raise nodes.SkipNode

        # @todo: Save the reference uris so they can be enumerated in the footer or something.
        self.write_to_buffer(':ref:`')

    def depart_reference(self, node):
        self.write_to_buffer('`')

    def visit_section(self, node):
        self.section_level += 1

    def depart_section(self, node):
        self.section_level -= 1

    def visit_strong(self, node):
        self.write_to_buffer('**')

    def depart_strong(self, node):
        self.write_to_buffer('**')

    def visit_subscript(self, node):
        self.write_to_buffer(':subscript:`')

    def depart_subscript(self, node):
        self.write_to_buffer('`')

    def visit_superscript(self, node):
        self.write_to_buffer(':superscript:`')

    def depart_superscript(self, node):
        self.write_to_buffer('`')

    def visit_term(self, node):
        pass

    def depart_term(self, node):
        pass

    def visit_title(self, node):
        pass

    def depart_title(self, node):
        text_length = self.buffer_length
        self.body.append(self.options.title_prefix[self.section_level])
        is_overlined = self.options.title_overline[self.section_level]
        if is_overlined:
            self.body.append(self.spacer)
            self.render_title_line(self.section_level, text_length)
            self.spacer = ''
        self.render_buffer()
        self.render_title_line(self.section_level, text_length)
        self.spacer = self.options.title_suffix[self.section_level]

    def visit_title_reference(self, node):
        self.write_to_buffer(':title-reference:`')

    def depart_title_reference(self, node):
        self.write_to_buffer('`')
