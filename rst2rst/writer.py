"""reStructuredText document tree Writer."""

__docformat__ = 'reStructuredText'

import textwrap

import docutils
from docutils import frontend, nodes, utils, writers, languages, io
from docutils.parsers.rst.states import Inliner
from docutils.transforms import writer_aux
from docutils.utils import roman
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

        self.list_style_stack = []
        """Stack of the styles to use for bullets or enumeration.

        For bullets, this is a suitable single character to use.

        For enumerations, this is an array containing the enumeration type,
        the prefix, the suffix, and a running count.

        Also used to determine the current level in nested lists.
        """

        self.list_finished = False
        """Signals that a list has finished.

        Currently only used to permit adding a newline between the last entry
        of a list and the next entry of its parent list.
        """

        self.external_targets = {
            'named': {},
            'anonymous': [],
        }
        """Stores external targets and the link names that point to them.

        These are then rendered at the end of a document, permitting indirect
        links to be used instead of outputting the same URI repeatedly.
        """

        self.buffer = []
        self.last_buffer_length = 0

        self.custom_roles = []
        self.ignore_inlines = False

        self.table_buffer = None

    # Dynamic properties

    @property
    def buffer_length(self):
        return len(''.join(self.buffer))

    @property
    def bullet_character(self):
        return self.options.bullet_character[len(self.list_style_stack)]

    @property
    def indentation(self):
        """Return current indentation as unicode."""
        return self.options.indentation_char * self.indentation_length

    @property
    def indentation_length(self):
        """Return length of current indentation."""
        return sum(self._indentation_levels)

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

    def register_role(self, role, options={}):
        if role in self.custom_roles:
            return
        self.custom_roles.append(role)

        text = '.. role:: %s\n' % role
        if options:
            self.indent(2)
            for option in options:
                text += '%s:%s: %s\n' % (self.indentation, option, options[option])
            self.dedent()
        self.roles.append(text)

    def render_buffer(self):
        """Append wrapped buffer to body."""
        if self.body:
            # Don't need a spacer if this is the first thing to be rendered
            self.body.append(self.spacer)
        text = ''.join(self.buffer)
        self.last_buffer_length = len(text)
        text = self.wrap(text) + '\n'
        self.body.append(text)
        self.buffer = []

    def render_buffer_to_table(self):
        col_idx = self.table_buffer['processing']['col']
        row_idx = self.table_buffer['processing']['row']
        if 'wrapping' in self.table_buffer['column_spec'][col_idx]:
            wrapping = self.table_buffer['column_spec'][col_idx]['wrapping']
        else:
            column_count = len(self.table_buffer['column_spec'])
            wrapping = int(
                (self.options.wrap_length - self.indentation_length - 1) / column_count
            ) - 3

        text = ''.join(self.buffer)
        self.last_buffer_length = len(text)
        text = self.wrap(text, wrapping).split('\n')

        if self.table_buffer['content'][row_idx][col_idx]:
            self.table_buffer['content'][row_idx][col_idx] += [""]
        self.table_buffer['content'][row_idx][col_idx] += text

        self.buffer = []

    def render_table(self):
        if self.body:
            # Don't need a spacer if this is the first thing to be rendered
            self.body.append(self.spacer)

        rows = self.table_buffer['content']
        columns = self.table_buffer['column_spec']

        column_count = len(columns)
        column_wrapping = []
        for col_idx in range(column_count):
            if 'wrapping' in columns[col_idx]:
                column_wrapping += [columns[col_idx]['wrapping']]
            else:
                column_wrapping += [0]
                for row in rows:
                    cell = row[col_idx]
                    for line in cell:
                        column_wrapping[col_idx] = max(column_wrapping[col_idx], len(line))

        self.render_table_hline(column_wrapping, False)

        for row_idx in range(len(rows)):
            row = rows[row_idx]

            line_count = 0
            for cell in row:
                line_count = max(line_count, len(cell))

            for line_idx in range(line_count):
                line_out = '|'
                for col_idx in range(column_count):
                    cell = row[col_idx]
                    line = cell[line_idx] if len(cell) > line_idx else ''
                    rpad = ' ' * (column_wrapping[col_idx] - len(line))
                    line_out += " %s%s |" % (line, rpad)
                self.body.append(line_out + "\n")

            self.render_table_hline(
                column_wrapping,
                self.table_buffer['heading_length'] == row_idx)

        # Clear table buffer
        self.table_buffer = None

    def render_table_hline(self, column_wrapping, double = False):
        dash = '=' if double else '-'
        hline = '+'
        for wrapping_width in column_wrapping:
            hline += dash * (wrapping_width + 2) + '+'
        self.body.append(hline + "\n")

    def render_external_targets(self):
        if not self.external_targets['anonymous'] and not self.external_targets['named']:
            return

        self.body.append('\n\n')

        # Print anonymous targets first, hoisting any non-anonymous targets
        # with the same uri.
        skip_uris = []
        for target_uri in self.external_targets['anonymous']:
            if target_uri in self.external_targets['named'] and target_uri not in skip_uris:
                skip_uris.append(target_uri)
                for indirect_name in sorted(self.external_targets['named'][target_uri]):
                    self.body.append('.. _`%s`:\n' % indirect_name)

            self.body.append('.. __: %s\n' % target_uri)

        # Print remaining non-anonymous targets, using indirect references
        # where possible.
        for target_uri in sorted(self.external_targets['named'].keys()):
            if target_uri in skip_uris:
                continue
            targets = sorted(self.external_targets['named'][target_uri])
            target_name = targets[0]
            self.body.append('.. _`%s`: %s\n' % (target_name, target_uri))

            for indirect_name in targets[1:]:
                self.body.append('.. _`%s`: _`%s`\n' % (indirect_name, target_name))

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
        self.list_finished = False
        self.list_style_stack.append(self.bullet_character)
        self.spacer = ''

    def depart_bullet_list(self, node):
        self.list_style_stack.pop()
        self.list_finished = True
        self.spacer = '\n'

    def visit_classifier(self, node):
        self.write_to_buffer(' : ')

    def depart_classifier(self, node):
        pass

    def visit_colspec(self, node):
        if 'colwidth' in node:
            self.table_buffer['column_spec'].append({
                'width': node['colwidth'],
                'wrapping': node['colwidth'] - 2,
            })
        else:
            self.table_buffer['column_spec'].append({})
        raise nodes.SkipNode

    def visit_definition(self, node):
        self.render_buffer()
        self.spacer = ''
        self.indent(2)

    def depart_definition(self, node):
        self.dedent()

    def visit_definition_list(self, node):
        self.spacer = '\n'

    def depart_definition_list(self, node):
        pass

    def visit_definition_list_item(self, node):
        pass

    def depart_definition_list_item(self, node):
        pass

    def depart_document(self, node):
        self.render_external_targets()
        if self.custom_roles:
            self.roles.append('\n')

    def visit_emphasis(self, node):
        self.write_to_buffer('*')

    def depart_emphasis(self, node):
        self.write_to_buffer('*')

    def visit_entry(self, node):
        self.table_buffer['processing']['col'] += 1

    def depart_entry(self, node):
        if 'morecols' in node:
            self.table_buffer['processing']['col'] += node['morecols']

    def visit_enumerated_list(self, node):
        self.body.append(self.spacer)
        self.list_finished = False
        self.list_style_stack.append([
            node.get('enumtype'),
            node.get('prefix'),
            node.get('suffix'),
            0
        ])
        self.spacer = ''

    def depart_enumerated_list(self, node):
        self.list_style_stack.pop()
        self.list_finished = True
        self.spacer = '\n'

    def visit_inline(self, node):
        if self.ignore_inlines:
            return
        classes = node.get('classes', [])
        for role in classes:
            self.register_role(role)
        classes = ' '.join(classes)
        self.write_to_buffer(':%s:`' % classes)

    def depart_inline(self, node):
        if self.ignore_inlines:
            return
        self.write_to_buffer('`')

    def visit_list_item(self, node):
        self.body.append(self.spacer)
        if self.list_finished:
            # Add a newline between the end of a list
            # and the next entry in its parent list.
            self.body.append('\n')
            self.list_finished = False

        style = self.list_style_stack[-1]
        if isinstance(style, str):
            indent = 2
            point = style
        else:
            self.list_style_stack[-1][3] += 1
            indent = 3
            point = style[3]
            if style[0].endswith('alpha'):
                point = chr(point + ord('a') - 1)
            elif style[0].endswith('roman'):
                point = roman.toRoman(point)

            if style[0].startswith('upper'):
                point = point.upper()

            point = "%s%s%s" % (style[1], point, style[2])

        self.indent(indent, '%s%s ' % (self.indentation, point))
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
        classes = node.get('classes', [])
        if classes and len(classes) > 1:
            options = {}
            if len(classes) == 3:
                options['language'] = classes[2]
            self.register_role('%s(code)' % classes[1], options)
            self.write_to_buffer(':%s:`' % classes[1])
            self.ignore_inlines = True
        else:
            self.write_to_buffer('``')

    def depart_literal(self, node):
        classes = node.get('classes', [])
        if classes and len(classes) > 1:
            self.write_to_buffer('`')
            self.ignore_inlines = False
        else:
            self.write_to_buffer('``')

    def visit_literal_block(self, node):
        # @todo: Support parsed-literal blocks
        # @todo: Support option "number-lines" and strip line numbers from the text
        # @todo: Check that line lengths don't exceed column width if table_buffer has no column widths set
        classes = node.get('classes', [])
        if classes:
            self.write_to_buffer('.. code:: %s' % classes[1])
        else:
            if self.body and len(self.body[-1]) > 1 and self.body[-1][-2] == ':':
                self.body[-1] = self.body[-1][:-2] + ':' + self.body[-1][-2:]
                self.spacer = ''
            else:
                self.write_to_buffer('::')
                self.spacer = '\n'

        if self.table_buffer:
            self.render_buffer_to_table()
            col_idx = self.table_buffer['processing']['col']
            row_idx = self.table_buffer['processing']['row']
            self.table_buffer['content'][row_idx][col_idx] += [""]
        else:
            self.render_buffer()
            self.body.append(self.spacer)
        self.spacer = '\n'

        self.indent(2)
        for line in node.astext().split('\n'):
            if self.table_buffer:
                self.table_buffer['content'][row_idx][col_idx].append('%s%s' % (self.indentation, line))
            else:
                self.body.append('%s%s\n' % (self.indentation, line))
        self.dedent()
        raise nodes.SkipNode

    def visit_math(self, node):
        self.write_to_buffer(':math:`')

    def depart_math(self, node):
        self.write_to_buffer('`')

    def visit_paragraph(self, node):
        text = node.astext()
        if len(text) > 1 and text[1] == '.' and text[0].isalpha():
            # Special case for things like the following, which shouldn't be
            # output in a way it can be misconstrued as a single-item list::
            #
            #   A. Einstein is a genius!
            #
            self.write_to_buffer('\\')

    def depart_paragraph(self, node):
        if self.table_buffer:
            self.render_buffer_to_table()
        else:
            self.render_buffer()
        self.spacer = '\n'
        self._indent_first_line[-1] = None

    def visit_reference(self, node):
        refuri = node.get('refuri')

        # Internal link
        if not refuri:
            self.write_to_buffer('`')
            return

        # External link
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

        if node.get('name'):
            # Text is not an explicitly given uri
            self.write_to_buffer('`')

    def depart_reference(self, node):
        if not node.get('refuri') or node.get('name'):
            self.write_to_buffer('`_')
            if node.get('anonymous'):
                self.write_to_buffer('_')

    def visit_row(self, node):
        self.table_buffer['processing']['row'] += 1
        self.table_buffer['processing']['col'] = -1
        self.table_buffer['content'].append([[] for i in range(len(self.table_buffer['column_spec']))])

    def depart_row(self, node):
        if self.table_buffer['processing']['is_header']:
            self.table_buffer['heading_length'] += 1

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

    def visit_table(self, node):
        self.table_buffer = {
            'content': [],
            'column_spec': [],
            'heading_length': -1,
            'processing': {
                'col': -1,
                'row': -1,
                'is_header': False,
            }
        }

    def depart_table(self, node):
        self.render_table()

    def visit_target(self, node):
        # Internal inline target
        if node.astext():
            self.write_to_buffer('_`')
            return

        # Internal block target
        refid = node.get('refid')
        if refid:
            ref_name = ''
            if docutils.__version__ < '0.18.1':
                findall_func = node.document.traverse # Deprecated in 0.18.1 onwards
            else:
                findall_func = node.document.findall
            # Find the name to use, as docutils doesn't pass it as part of the node.
            for candidate in findall_func(condition=nodes.reference):
                candidate_refid = candidate.get('refid')
                if candidate_refid and candidate_refid == refid:
                    ref_name = candidate.get('name')
                    break;

            if not ref_name:
                # In the case that the internal target actually points to an
                # external hyperlink target placed below it.
                raise nodes.SkipNode

            # Use buffer (instead of writing directly) to get indentation if set.
            self.write_to_buffer(".. _`%s`:" % ref_name)
            self.render_buffer()
            raise nodes.SkipNode

        # External target
        refuri = node.get('refuri')
        if node.get('anonymous'):
            self.external_targets['anonymous'].append(refuri)

        if refuri not in self.external_targets['named']:
            self.external_targets['named'][refuri] = []
        targets = self.external_targets['named'][refuri]

        names = node.get('names')
        for idx in range(len(names)):
            if names[idx] in targets:
                continue
            targets.append(names[idx])
        raise nodes.SkipNode

    def depart_target(self, node):
        # This is only called if this was an internal inline target.
        self.write_to_buffer('`')

    def visit_tbody(self, node):
        pass

    def depart_tbody(self, node):
        pass

    def visit_term(self, node):
        pass

    def depart_term(self, node):
        pass

    def visit_tgroup(self, node):
        pass

    def depart_tgroup(self, node):
        pass

    def visit_thead(self, node):
        self.table_buffer['processing']['is_header'] = True

    def depart_thead(self, node):
        self.table_buffer['processing']['is_header'] = False

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
