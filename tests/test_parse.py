"""Tests for parse.py: WikilinkExtractor and parse_document."""

import itertools
import re
from pathlib import Path

import pytest

from graphmark.model import Document
from graphmark.parse import (
    MarkdownLinkExtractor,
    WikilinkExtractor,
    count_markdown_links,
    parse_document,
)

FIXTURE_VAULT = Path(__file__).parent / "fixtures" / "simple" / "vault"


class TestWikilinkExtractor:
    def setup_method(self):
        self.extractor = WikilinkExtractor()

    def test_extracts_bare_link(self):
        assert self.extractor.extract("See [[Note]].") == ["Note"]

    def test_extracts_multiple_links(self):
        assert self.extractor.extract("Links to [[alpha]], [[beta]], and [[gamma]].") == [
            "alpha",
            "beta",
            "gamma",
        ]

    def test_extracts_raw_alias_display(self):
        # Extractor returns the raw display; alias stripping is the resolver's job
        assert self.extractor.extract("See [[Alpha|the first note]].") == ["Alpha|the first note"]

    def test_extracts_anchor_display(self):
        # Anchor stripping is also the resolver's job
        assert self.extractor.extract("See [[Note#Section]].") == ["Note#Section"]

    def test_excludes_inline_code_span(self):
        assert self.extractor.extract("Inline: `[[ignored]]`.") == []

    def test_excludes_link_in_fenced_block_backtick(self):
        text = "Before.\n```\n[[hidden]]\n```\nAfter."
        assert self.extractor.extract(text) == []

    def test_excludes_link_in_fenced_block_tilde(self):
        text = "Before.\n~~~\n[[hidden]]\n~~~\nAfter."
        assert self.extractor.extract(text) == []

    def test_link_before_code_span_not_excluded(self):
        assert self.extractor.extract("`code` and [[real]].") == ["real"]

    def test_shorter_nested_fence_does_not_close_longer_outer_fence(self):
        # A 4-backtick outer fence wrapping a 3-backtick example: the inner 3-backtick
        # lines must NOT close the outer fence, so [[hidden]] stays inside code.
        text = "````\n```\ninner [[hidden]]\n```\n````\nAfter [[real]].\n"
        result = self.extractor.extract(text)
        assert "hidden" not in result
        assert result == ["real"]

    def test_fence_line_with_trailing_content_does_not_close_the_block(self):
        # A same-length fence run followed by an info string (e.g. a nested ```python line
        # documenting Markdown syntax) is not a closer — only the true closer below it is.
        text = "```\nHow to open a python block:\n```python\ncode here\n```\nAfter [[real]].\n"
        assert self.extractor.extract(text) == ["real"]

    def test_fence_closer_with_trailing_whitespace_still_closes(self):
        text = "```\n[[hidden]]\n```   \nAfter [[real]].\n"
        result = self.extractor.extract(text)
        assert "hidden" not in result
        assert result == ["real"]

    def test_four_space_indented_unbalanced_fence_does_not_swallow_a_later_link(self):
        # False-open (#260): a 4+-space-indented ``` run is an indented code block, not a
        # fence delimiter, per CommonMark's 0-3-space budget. Left unbalanced (no matching
        # false-positive close), it must not swallow every remaining line to EOF.
        text = "    ```\nAfter [[real]].\n"
        assert self.extractor.extract(text) == ["real"]

    def test_four_space_indented_line_does_not_close_a_real_fence(self):
        # False-close (#260), symmetric to the above: once a real (0-3 space) fence is open,
        # a 4+-space-indented ``` line inside it is not a closer either — it is ordinary
        # fenced content, dropped like any other line inside the block. Only the true
        # (0-indent) closer below it ends the block.
        text = (
            "```\n[[hidden]]\n    ```\n[[still-hidden-if-fence-stayed-open]]\n```\nSee [[real]].\n"
        )
        result = self.extractor.extract(text)
        assert "hidden" not in result
        assert "still-hidden-if-fence-stayed-open" not in result
        assert result == ["real"]

    def test_fence_indented_two_spaces_still_opens_and_closes(self):
        text = "  ```\n[[hidden]]\n  ```\nAfter [[real]].\n"
        result = self.extractor.extract(text)
        assert "hidden" not in result
        assert result == ["real"]

    def test_fence_indented_exactly_three_spaces_still_opens_and_closes(self):
        # The CommonMark boundary: 3 raw characters of leading whitespace is still within the
        # 0-3 budget on both the open and the close side.
        text = "   ```\n[[hidden]]\n   ```\nAfter [[real]].\n"
        result = self.extractor.extract(text)
        assert "hidden" not in result
        assert result == ["real"]

    def test_tab_indented_fence_counts_as_one_raw_character_and_still_opens_and_closes(self):
        # A tab is counted as a single raw character of indentation (not expanded to a
        # CommonMark 4-column tab stop) — a documented simplification. 1 <= 3, so this is
        # still a real fence on both the open and the close side.
        text = "\t```\n[[hidden]]\n\t```\nAfter [[real]].\n"
        result = self.extractor.extract(text)
        assert "hidden" not in result
        assert result == ["real"]

    def test_hub_md_links(self):
        # Matches hub.md content exactly — the definitive integration test for the extractor
        text = (
            "Links to [[alpha]], [[beta]], and [[gamma]]. "
            "Also an alias link to [[Alpha|the first note]].\n\n"
            "A code-span link that must be ignored: `[[ignored]]`."
        )
        result = self.extractor.extract(text)
        assert set(result) == {"alpha", "beta", "gamma", "Alpha|the first note"}
        assert "ignored" not in result


#: Separators that put a BLANK line between two lines: empty, spaces/tabs only, and the CRLF forms
#: of both. A blank line ends the paragraph, so no inline code span may reach across one.
BLANK_LINE_SEPARATORS = [
    pytest.param("\n\n", id="lf"),
    pytest.param("\n  \t\n", id="lf-spaces-and-tab"),
    pytest.param("\r\n\r\n", id="crlf"),
    pytest.param("\r\n \t\r\n", id="crlf-spaces-and-tab"),
]


class TestInlineCodeSpanForms:
    """Pins what an inline code span hides today (#289), before a span may wrap a line break.

    Every case is green on the single-line-only regex and has to stay green once a span may wrap
    one line break: the widening may ADD hidden regions that wrap a break, and nothing else. It must
    not touch a single-line span, an unterminated backtick, the text between spans, or a span that
    a blank line separates from its partner backtick.
    """

    def setup_method(self):
        self.extractor = WikilinkExtractor()

    def test_a_single_line_span_hides_its_own_link_and_nothing_around_it(self):
        text = "Before [[A]] `[[Hidden]]` after [[B]]."
        assert self.extractor.extract(text) == ["A", "B"]

    def test_text_between_two_spans_on_one_line_stays_visible(self):
        assert self.extractor.extract("`[[X]]` then [[Between]] then `[[Y]]`") == ["Between"]

    def test_adjacent_backticks_are_not_a_span_and_hide_nothing_after_them(self):
        assert self.extractor.extract("empty `` then [[Visible]] to the end") == ["Visible"]

    def test_a_lone_backtick_hides_nothing_on_its_own_line(self):
        assert self.extractor.extract("a stray ` then [[Visible]] to the end") == ["Visible"]

    def test_an_unterminated_backtick_hides_nothing_on_the_lines_after_it(self):
        # No closing backtick anywhere: the opener must not swallow the lines that follow it.
        text = "a stray `tick here\nthen [[Visible]]\nto the end\n"
        assert self.extractor.extract(text) == ["Visible"]

    @pytest.mark.parametrize("sep", BLANK_LINE_SEPARATORS)
    def test_a_blank_line_between_two_backticks_ends_the_span(self, sep):
        # A blank line ends the paragraph, and with it any open backtick: both links stay visible.
        text = f"`[[First]] code with{sep}[[Second]] more`"
        assert self.extractor.extract(text) == ["First", "Second"]

    def test_a_crlf_single_line_span_hides_its_link_and_nothing_around_it(self):
        text = "Pre [[A]]\r\n`[[Hidden]]` mid\r\nPost [[B]]\r\n"
        assert self.extractor.extract(text) == ["A", "B"]

    def test_a_span_next_to_a_fenced_block_hides_only_its_own_link(self):
        text = "`[[Hidden]]`\n```\n[[Inside]]\n```\n`[[AlsoHidden]]` [[Visible]]\n"
        assert self.extractor.extract(text) == ["Visible"]

    def test_prose_between_two_triple_backtick_spans_on_adjacent_lines_stays_visible(self):
        # A ```x``` run leaves two end backticks behind on each side. They must not pair across
        # the line break and hide the prose between the two spans (a real link, `[[Real]]`).
        text = "- ```a```: see [[Real]]\n- ```b```: more\n"
        assert self.extractor.extract(text) == ["Real"]

    def test_a_backtick_run_longer_than_one_does_not_open_a_span_across_a_line_break(self):
        assert self.extractor.extract("``a [[Visible]]\nb`") == ["Visible"]

    def test_a_backtick_run_longer_than_one_does_not_close_a_span_across_a_line_break(self):
        assert self.extractor.extract("`a [[Visible]]\nb``") == ["Visible"]

    def test_an_escaped_backtick_does_not_open_a_span_across_a_line_break(self):
        # A backslash-escaped backtick is a literal, not a delimiter: the real span `x` on the
        # next line is the only code here, so the link before it stays visible.
        assert self.extractor.extract("type \\` then [[Visible]]\nand `x` more") == ["Visible"]

    def test_a_text_with_no_line_break_is_stripped_exactly_as_the_single_line_regex_did(self):
        # The invariant behind the widening: the wrapped alternative needs a line break to match,
        # so a text without one must be stripped byte for byte as before. The legacy regex is
        # pinned verbatim; every string over an alphabet of backticks, text, a bracket, a space,
        # a CR and a backslash (up to 7 long) must strip identically -- empty spans, backtick runs,
        # escaped backticks and all.
        from graphmark.parse import _INLINE_CODE_RE

        legacy = re.compile(r"`[^`\n]+`")
        for length in range(1, 8):
            for chars in itertools.product("`a [\r\\", repeat=length):
                text = "".join(chars)
                assert _INLINE_CODE_RE.sub("", text) == legacy.sub("", text), repr(text)


class TestInlineCodeSpanWrapsOneLineBreak:
    """An inline code span may wrap one line break (#289).

    CommonMark and Obsidian render ``See `code with\\n[[Note]]` end.`` as one code span, so the link
    is code, not a link. Only a blank line ends the paragraph (and with it the span) -- that half is
    pinned in `TestInlineCodeSpanForms`. The tests here put a hidden link inside the wrapped span
    AND a visible link next to it, so they fail both on a span that is not stripped and on one that
    swallows the text around it. A span over two or more breaks is out of scope and deliberately
    not pinned either way.
    """

    def setup_method(self):
        self.extractor = WikilinkExtractor()

    def test_a_link_on_the_second_line_of_a_wrapped_span_is_hidden(self):
        assert self.extractor.extract("See `code with\n[[Hidden Note]]` end.") == []

    def test_a_link_on_the_first_line_of_a_wrapped_span_is_hidden(self):
        assert self.extractor.extract("See `[[Hidden Note]] code\nmore` end.") == []

    def test_links_on_both_lines_of_a_wrapped_span_are_hidden(self):
        assert self.extractor.extract("See `[[One]] and\n[[Two]]` end.") == []

    def test_a_link_on_the_second_line_of_a_crlf_wrapped_span_is_hidden(self):
        assert self.extractor.extract("See `code with\r\n[[Hidden Note]]` end.") == []

    def test_a_link_on_the_first_line_of_a_crlf_wrapped_span_is_hidden(self):
        assert self.extractor.extract("See `[[Hidden Note]] code\r\nmore` end.") == []

    @pytest.mark.parametrize(
        "text",
        [
            pytest.param(
                "- Item `code with\n  [[Hidden]]` end. [[Visible]]", id="list-continuation"
            ),
            pytest.param(
                "- Item `code with\n\t[[Hidden]]` end. [[Visible]]", id="tab-continuation"
            ),
            pytest.param("> Quote `code with\n> [[Hidden]]` end. [[Visible]]", id="blockquote"),
        ],
    )
    def test_a_wrapped_span_whose_second_line_is_indented_or_quoted_hides_its_link(self, text):
        # The hard-wrap shapes real notes use: a list item's indented continuation line, a tab,
        # and a blockquote's `> ` prefix. The second line need not start at column 0.
        assert self.extractor.extract(text) == ["Visible"]

    def test_text_before_and_after_a_wrapped_span_stays_visible(self):
        text = "[[Before]] See `code with\n[[Hidden Note]]` end. [[After]]"
        assert self.extractor.extract(text) == ["Before", "After"]

    def test_text_before_and_after_a_crlf_wrapped_span_stays_visible(self):
        text = "[[Before]] See `code with\r\n[[Hidden Note]]` end. [[After]]"
        assert self.extractor.extract(text) == ["Before", "After"]

    def test_a_link_after_a_closed_wrapped_span_on_the_same_line_stays_visible(self):
        assert self.extractor.extract("`code with\n[[Hidden]]` [[Visible]]") == ["Visible"]

    def test_a_link_on_the_line_after_a_wrapped_span_stays_visible(self):
        text = "`code with\n[[Hidden]]`\n[[Visible]]\n"
        assert self.extractor.extract(text) == ["Visible"]

    def test_a_link_between_two_wrapped_spans_stays_visible(self):
        text = "`a\n[[Hidden One]]` [[Between]] `[[Hidden Two]]\nb`"
        assert self.extractor.extract(text) == ["Between"]

    def test_a_link_between_a_plain_and_a_wrapped_span_on_adjacent_lines_stays_visible(self):
        text = "`[[Hidden One]]`\n[[Between]]\n`a\n[[Hidden Two]]`"
        assert self.extractor.extract(text) == ["Between"]

    def test_a_link_between_a_wrapped_span_and_a_single_line_span_stays_visible(self):
        # The wrapped alternative must stop at its own closing backtick: a swallow tail that
        # reaches over the following single-line span would hide `[[Between]]` too.
        text = "`a\n[[Hidden One]]` [[Between]] `[[Hidden Two]]`"
        assert self.extractor.extract(text) == ["Between"]

    def test_a_link_between_a_single_line_span_and_a_wrapped_span_stays_visible(self):
        # The reverse order: the first line's run must stop at the nearest backtick, not run on to
        # the last one on its line and open a wrapped span there.
        text = "`[[Hidden One]]` [[Between]] `a\n[[Hidden Two]]`"
        assert self.extractor.extract(text) == ["Between"]

    def test_a_link_between_two_single_line_spans_on_adjacent_lines_stays_visible(self):
        assert self.extractor.extract("`[[One]]`\n[[Between]]\n`[[Two]]`") == ["Between"]

    @pytest.mark.parametrize("eol", [pytest.param("\n", id="lf"), pytest.param("\r\n", id="crlf")])
    def test_an_opening_backtick_that_ends_its_line_wraps_nothing_under_either_line_ending(
        self, eol
    ):
        # Known limit: CommonMark would pair a backtick that ends its line with the closing one
        # on the next line, graphmark does not. What is pinned is that LF and CRLF agree: the
        # lone CR of a CRLF break must not stand in for the line's missing first character.
        text = f"See `{eol}[[Hidden]]` end [[Visible]]"
        assert self.extractor.extract(text) == ["Hidden", "Visible"]

    def test_a_text_is_stripped_the_same_under_lf_and_crlf_line_endings(self):
        # P4: converting every LF of a text to CRLF must not change which regions are code. Every
        # string over a short alphabet of backticks, text, a space, a line break and a backslash
        # (up to 7 long), compared after folding the CRLFs back to LF.
        from graphmark.parse import _INLINE_CODE_RE

        for length in range(1, 8):
            for chars in itertools.product("`a \n\\", repeat=length):
                lf = "".join(chars)
                crlf = lf.replace("\n", "\r\n")
                stripped_crlf = _INLINE_CODE_RE.sub("", crlf).replace("\r\n", "\n")
                assert stripped_crlf == _INLINE_CODE_RE.sub("", lf), repr(lf)

    @pytest.mark.parametrize("eol", [pytest.param("\n", id="lf"), pytest.param("\r\n", id="crlf")])
    @pytest.mark.parametrize(
        "template",
        [
            pytest.param("[[Real Note `x{eol}y`]]", id="span-at-the-end-of-the-target"),
            pytest.param("[[A `x{eol}y` B]]", id="span-in-the-middle-of-the-target"),
            pytest.param("Straddle: [[Real Note `x{eol}y`]] done.", id="inside-a-sentence"),
        ],
    )
    def test_a_wrapped_span_inside_a_wikilink_target_does_not_splice_a_link_together(
        self, template, eol
    ):
        # `_WIKILINK_RE` is line-oriented: `.` excludes the line break, so a link never spans one.
        # Deleting the wrapped span with its break would join the two lines and let `[[` reach a
        # `]]` it could not reach in the original text, conjuring a link out of code.
        assert self.extractor.extract(template.format(eol=eol)) == []

    @pytest.mark.parametrize("eol", [pytest.param("\n", id="lf"), pytest.param("\r\n", id="crlf")])
    def test_a_wrapped_span_does_not_swallow_the_opening_brackets_of_a_real_link(self, eol):
        # The span `x]] z{eol}y` starts inside the first link's brackets and ends before the real
        # one. Splicing the lines would let `[[Other ` pair with the real link's `]]` and eat its
        # `[[`, losing "Real Note" for an unresolved garbage target.
        text = f"[[Other `x]] z{eol}y` and [[Real Note]]."
        assert self.extractor.extract(text) == ["Real Note"]

    def test_a_wrapped_span_and_a_blank_line_that_ends_a_span_in_one_text(self):
        # The first pair of backticks wraps one break and is code; the second pair is split by a
        # blank line and is not, so the link between them is a real one.
        text = "See `a\nb` and `c\n\n[[Visible]] d`"
        assert self.extractor.extract(text) == ["Visible"]

    def test_a_wrapped_span_beside_a_fenced_block_hides_only_its_own_link(self):
        text = "Intro `code with\n[[Hidden]]` end.\n```\n[[Inside]]\n```\n[[Visible]]\n"
        assert self.extractor.extract(text) == ["Visible"]

    def test_the_helper_deletes_a_single_line_span_outright_but_keeps_a_wrapped_spans_break(self):
        # `_strip_non_link_regions` is the one place spans are removed for all three consumers.
        # A single-line span leaves nothing behind (as before this change); a wrapped span leaves
        # one line break, so deleting it cannot splice two lines into one. Pinned on the helper
        # itself: through the public extractors a single-line span that wrongly left a break would
        # only show on a link that has a code span inside it.
        from graphmark.parse import _strip_non_link_regions

        assert _strip_non_link_regions("See `x` end.") == "See  end."
        assert _strip_non_link_regions("See `x\ny` end.") == "See \n end."
        assert _strip_non_link_regions("See `x\r\ny` end.") == "See \n end."


class TestParseDocument:
    def test_returns_document_type(self):
        doc = parse_document(FIXTURE_VAULT / "brain" / "alpha.md", FIXTURE_VAULT)
        assert isinstance(doc, Document)

    def test_rel_path_is_posix(self):
        doc = parse_document(FIXTURE_VAULT / "brain" / "alpha.md", FIXTURE_VAULT)
        assert doc.rel_path == "brain/alpha.md"

    def test_rel_path_subdirectory(self):
        doc = parse_document(FIXTURE_VAULT / "personal" / "beta.md", FIXTURE_VAULT)
        assert doc.rel_path == "personal/beta.md"

    def test_body_contains_note_content(self):
        doc = parse_document(FIXTURE_VAULT / "brain" / "alpha.md", FIXTURE_VAULT)
        assert "[[beta]]" in doc.text

    def test_body_does_not_start_with_frontmatter_delimiter(self):
        doc = parse_document(FIXTURE_VAULT / "brain" / "alpha.md", FIXTURE_VAULT)
        assert not doc.text.lstrip().startswith("---")

    def test_frontmatter_keys_parsed(self):
        doc = parse_document(FIXTURE_VAULT / "brain" / "alpha.md", FIXTURE_VAULT)
        assert "date" in doc.frontmatter
        assert "description" in doc.frontmatter
        assert "tags" in doc.frontmatter

    def test_no_frontmatter_file(self, tmp_path):
        note = tmp_path / "plain.md"
        note.write_text("# Plain\n\nSome [[link]] here.")
        doc = parse_document(note, tmp_path)
        assert doc.frontmatter == {}
        assert "[[link]]" in doc.text

    def test_invalid_utf8_decodes_with_replacement_and_warns(self, tmp_path, capsys):
        note = tmp_path / "bad.md"
        # 0xff is not valid UTF-8; the rest is decodable.
        note.write_bytes(b"# Bad\n\nSome [[link]] and a bad byte: \xff end.\n")
        doc = parse_document(note, tmp_path)
        assert isinstance(doc, Document)
        assert doc.rel_path == "bad.md"
        assert "[[link]]" in doc.text  # decodable content survives
        captured = capsys.readouterr()
        assert captured.out == ""  # never pollute stdout / the JSON surface
        assert "bad.md" in captured.err
        assert "invalid UTF-8" in captured.err

    def test_valid_utf8_file_emits_no_warning(self, tmp_path, capsys):
        note = tmp_path / "good.md"
        note.write_text("# Good\n\nAll clean [[link]].\n", encoding="utf-8")
        parse_document(note, tmp_path)
        captured = capsys.readouterr()
        assert captured.err == ""

    def test_unterminated_fence_warns_exactly_once(self, tmp_path, capsys):
        note = tmp_path / "unterminated.md"
        note.write_text(
            "See [[before]].\n```\ncode line\n[[inside]]\nSee [[after]].\n",
            encoding="utf-8",
        )
        doc = parse_document(note, tmp_path)
        assert isinstance(doc, Document)
        # Existing behavior unchanged: parse_document's own body is unaffected (fence stripping
        # is the extractor's job, not parse_document's) -- content after the unclosed fence is
        # still dropped only once an extractor runs, exactly as before this change.
        assert "[[after]]" not in WikilinkExtractor().extract(doc.text)
        captured = capsys.readouterr()
        assert captured.out == ""  # never pollute stdout / the JSON surface
        warning_lines = [line for line in captured.err.splitlines() if line]
        assert len(warning_lines) == 1
        assert warning_lines[0] == (
            "graphmark: warning: unterminated.md: unterminated fenced code block, "
            "trailing content dropped"
        )

    def test_closed_fence_emits_no_unterminated_fence_warning(self, tmp_path, capsys):
        note = tmp_path / "closed.md"
        note.write_text(
            "See [[before]].\n```\ncode line\n```\nSee [[after]].\n",
            encoding="utf-8",
        )
        doc = parse_document(note, tmp_path)
        assert "[[after]]" in doc.text
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == ""

    def test_no_fence_at_all_emits_no_unterminated_fence_warning(self, tmp_path, capsys):
        note = tmp_path / "plain.md"
        note.write_text("Just prose with [[a-link]], no fences at all.\n", encoding="utf-8")
        parse_document(note, tmp_path)
        captured = capsys.readouterr()
        assert captured.err == ""

    def test_unterminated_fence_warning_fires_once_under_default_link_syntax(
        self, tmp_path, capsys
    ):
        # Simulates a real build under the default `link_syntax="wikilink"`: parse_document
        # runs once, then WikilinkExtractor.extract and count_markdown_links each run over the
        # same body (VaultGraph.build calls WikilinkExtractor per config, and
        # _warn_if_unread_syntax_dominates calls count_markdown_links unconditionally). All
        # three call `_strip_fenced_blocks` on the same unterminated-fence body, but only
        # parse_document's own call may ever print the warning.
        note = tmp_path / "unterminated.md"
        body = "See [[before]].\n```\ncode line\n[[inside]]\nSee [[after]].\n"
        note.write_text(body, encoding="utf-8")

        doc = parse_document(note, tmp_path)
        WikilinkExtractor().extract(doc.text)
        count_markdown_links(doc.text)

        captured = capsys.readouterr()
        warning_lines = [line for line in captured.err.splitlines() if line]
        assert len(warning_lines) == 1

    def test_unterminated_fence_warning_fires_once_under_link_syntax_both(self, tmp_path, capsys):
        # Same simulation, but for `link_syntax="both"`: MarkdownLinkExtractor also runs over
        # the same body, for a third call into `_strip_fenced_blocks`.
        note = tmp_path / "unterminated.md"
        body = "See [[before]].\n```\ncode line\n[[inside]]\nSee [[after]].\n"
        note.write_text(body, encoding="utf-8")

        doc = parse_document(note, tmp_path)
        WikilinkExtractor().extract(doc.text)
        MarkdownLinkExtractor().extract(doc.text)
        count_markdown_links(doc.text)

        captured = capsys.readouterr()
        warning_lines = [line for line in captured.err.splitlines() if line]
        assert len(warning_lines) == 1


class TestFrontmatterLineEndings:
    """CRLF notes (Windows / git autocrlf vaults) must parse identically to their LF twins.

    A frontmatter block that fails to split stays in the body, so a frontmatter wikilink
    (`related: "[[X]]"` — a common Obsidian pattern) becomes a phantom graph edge.
    """

    FM_BYTES_LF = b'---\ntitle: Note\nrelated: "[[Other Note]]"\n---\nBody with [[Real Link]].\n'
    FM_BYTES_CRLF = (
        b'---\r\ntitle: Note\r\nrelated: "[[Other Note]]"\r\n---\r\nBody with [[Real Link]].\r\n'
    )

    def _parse(self, tmp_path, name: str, data: bytes):
        note = tmp_path / name
        note.write_bytes(data)
        return parse_document(note, tmp_path)

    def test_crlf_frontmatter_matches_lf_twin(self, tmp_path):
        lf = self._parse(tmp_path, "lf.md", self.FM_BYTES_LF)
        crlf = self._parse(tmp_path, "crlf.md", self.FM_BYTES_CRLF)
        assert crlf.frontmatter == lf.frontmatter
        assert crlf.frontmatter == {"title": "Note", "related": "[[Other Note]]"}

    def test_crlf_frontmatter_wikilink_is_not_a_phantom_link(self, tmp_path):
        crlf = self._parse(tmp_path, "crlf.md", self.FM_BYTES_CRLF)
        links = WikilinkExtractor().extract(crlf.text)
        # "Other Note" lives in frontmatter — it must never reach the extractor.
        assert "Other Note" not in links
        assert links == ["Real Link"]

    def test_crlf_body_survives_the_split(self, tmp_path):
        crlf = self._parse(tmp_path, "crlf.md", self.FM_BYTES_CRLF)
        assert not crlf.text.lstrip().startswith("---")
        assert "[[Real Link]]" in crlf.text

    def test_closing_delimiter_at_eof_without_trailing_newline(self, tmp_path):
        # A frontmatter-only note (no body, no trailing newline) is legitimate; parse it.
        doc = self._parse(tmp_path, "fm_only.md", b"---\ntitle: Note\n---")
        assert doc.frontmatter == {"title": "Note"}
        assert doc.text == ""

    def test_closing_delimiter_at_eof_crlf(self, tmp_path):
        doc = self._parse(tmp_path, "fm_only_crlf.md", b"---\r\ntitle: Note\r\n---")
        assert doc.frontmatter == {"title": "Note"}
        assert doc.text == ""

    def test_trailing_spaces_on_opening_delimiter(self, tmp_path):
        # A paste or auto-format can leave `---  ` on the opening line; it is still a delimiter.
        data = self.FM_BYTES_LF.replace(b"---\ntitle", b"---  \ntitle", 1)
        assert data != self.FM_BYTES_LF
        doc = self._parse(tmp_path, "open_space.md", data)
        assert doc.frontmatter == {"title": "Note", "related": "[[Other Note]]"}
        assert not doc.text.lstrip().startswith("---")

    def test_trailing_tab_on_closing_delimiter(self, tmp_path):
        data = self.FM_BYTES_LF.replace(b'"\n---\n', b'"\n---\t\n', 1)
        assert data != self.FM_BYTES_LF
        doc = self._parse(tmp_path, "close_tab.md", data)
        assert doc.frontmatter == {"title": "Note", "related": "[[Other Note]]"}
        assert doc.text.strip() == "Body with [[Real Link]]."

    def test_trailing_whitespace_frontmatter_wikilink_is_not_a_phantom_link(self, tmp_path):
        data = b'---  \ntitle: Note\nrelated: "[[Other Note]]"\n---\t\nBody with [[Real Link]].\n'
        doc = self._parse(tmp_path, "both.md", data)
        links = WikilinkExtractor().extract(doc.text)
        assert "Other Note" not in links
        assert links == ["Real Link"]

    def test_empty_frontmatter_block(self, tmp_path):
        # Two adjacent `---` lines (a template stub or a cleared Properties block) are an empty
        # frontmatter block: it must split off, not stay in the body.
        doc = self._parse(tmp_path, "empty_fm.md", b"---\n---\nBody [[X]].\n")
        assert doc.frontmatter == {}
        assert doc.text == "Body [[X]].\n"

    def test_empty_frontmatter_block_crlf(self, tmp_path):
        doc = self._parse(tmp_path, "empty_fm_crlf.md", b"---\r\n---\r\nBody [[X]].\r\n")
        assert doc.frontmatter == {}
        assert doc.text == "Body [[X]].\r\n"

    def test_bare_rule_without_closing_delimiter_is_not_frontmatter(self, tmp_path):
        # A note opening with a horizontal rule and no closing `---` has no frontmatter at all.
        data = b"---\nBody [[X]].\n"
        doc = self._parse(tmp_path, "hr_open.md", data)
        assert doc.frontmatter == {}
        assert doc.text == data.decode()

    def test_empty_block_does_not_swallow_a_later_body_rule(self, tmp_path):
        # The optional block must be lazy: an empty block followed by a `---` rule in the body
        # must close at the second line, not stretch to the body's rule.
        doc = self._parse(tmp_path, "empty_then_rule.md", b"---\n---\nBody\n---\nmore\n")
        assert doc.frontmatter == {}
        assert doc.text == "Body\n---\nmore\n"


class TestBlockStyleLists:
    """`key:` followed by `  - item` lines — what Obsidian's Properties UI actually writes.

    The parser handled scalars, quoted strings and inline lists, but a block list's item lines
    contain no `:` so the loop skipped them, and the bare `key:` line stored `''`. Every
    block-style property in a real vault — `aliases:`, `tags:` — silently became an empty string
    rather than a list. Not an error, just quietly wrong data behind a public attribute.
    """

    def _fm(self, raw: str) -> dict:
        from graphmark.parse import _parse_frontmatter

        return _parse_frontmatter(raw)

    def test_block_list_parses_to_a_list(self):
        assert self._fm("aliases:\n  - One\n  - Two") == {"aliases": ["One", "Two"]}

    def test_a_single_item_block_is_still_a_list(self):
        assert self._fm("tags:\n  - project") == {"tags": ["project"]}

    def test_inline_lists_are_unchanged(self):
        assert self._fm("aliases: [One, Two]") == {"aliases": ["One", "Two"]}

    def test_scalars_are_unchanged(self):
        assert self._fm("title: Solo") == {"title": "Solo"}

    def test_quoted_scalars_are_unchanged(self):
        assert self._fm('description: "a thing"') == {"description": "a thing"}

    def test_an_empty_key_stays_an_empty_string(self):
        # A key with no items is an empty VALUE, not an empty list — unchanged behavior.
        assert self._fm("aliases:\ndate: 2026-07-25") == {"aliases": "", "date": "2026-07-25"}

    def test_the_block_ends_at_the_next_key(self):
        parsed = self._fm("aliases:\n  - One\n  - Two\ndate: 2026-07-25\ntitle: T")
        assert parsed == {"aliases": ["One", "Two"], "date": "2026-07-25", "title": "T"}

    def test_a_stray_item_after_another_key_is_not_absorbed(self):
        # The block must CLOSE at the next key, not merely pause. Without that, a malformed or
        # mid-edit note silently grows the earlier list — the fail-soft promise says drop the
        # junk, not misattribute it.
        parsed = self._fm("aliases:\n  - One\ndate: 2026-07-25\n  - Stray")
        assert parsed == {"aliases": ["One"], "date": "2026-07-25"}

    def test_a_colon_bearing_stray_item_is_not_absorbed_as_a_key(self):
        # Same junk as the colonless stray item, but its text holds a colon. With no list open it
        # must still be dropped, not partitioned as "- Note": "Subtitle".
        parsed = self._fm("aliases:\n  - One\ndate: 2026-07-25\n  - Note: Subtitle")
        assert parsed == {"aliases": ["One"], "date": "2026-07-25"}

    def test_two_block_lists_in_one_document(self):
        parsed = self._fm("aliases:\n  - A\ntags:\n  - x\n  - y")
        assert parsed == {"aliases": ["A"], "tags": ["x", "y"]}

    def test_quoted_block_items_are_unquoted(self):
        assert self._fm("aliases:\n  - \"Mood Tracker\"\n  - 'mood-tracker'") == {
            "aliases": ["Mood Tracker", "mood-tracker"]
        }

    def test_a_trailing_unpaired_quote_is_preserved_in_a_scalar(self):
        assert self._fm("title: Believin'") == {"title": "Believin'"}

    def test_a_trailing_unpaired_quote_is_preserved_in_a_block_item(self):
        assert self._fm("aliases:\n  - Believin'") == {"aliases": ["Believin'"]}

    def test_a_trailing_unpaired_quote_is_preserved_in_an_inline_list_item(self):
        assert self._fm("aliases: [Believin', Other]") == {"aliases": ["Believin'", "Other"]}

    def test_internal_apostrophes_with_no_wrapping_quotes_are_untouched(self):
        assert self._fm("title: Rock 'n' Roll") == {"title": "Rock 'n' Roll"}
        assert self._fm("aliases:\n  - Rock 'n' Roll") == {"aliases": ["Rock 'n' Roll"]}
        assert self._fm("aliases: [Rock 'n' Roll, Other]") == {
            "aliases": ["Rock 'n' Roll", "Other"]
        }

    def test_paired_single_quotes_are_unwrapped_at_every_site(self):
        assert self._fm("title: 'quoted'") == {"title": "quoted"}
        assert self._fm("aliases:\n  - 'quoted'") == {"aliases": ["quoted"]}
        assert self._fm("aliases: ['quoted', Other]") == {"aliases": ["quoted", "Other"]}

    def test_paired_double_quotes_are_unwrapped_at_every_site(self):
        assert self._fm('title: "quoted"') == {"title": "quoted"}
        assert self._fm('aliases:\n  - "quoted"') == {"aliases": ["quoted"]}
        assert self._fm('aliases: ["quoted", Other]') == {"aliases": ["quoted", "Other"]}

    def test_mismatched_quote_pairs_are_not_unwrapped(self):
        # A pair must be the SAME character at both ends; `"x'` is not a quoted value.
        assert self._fm("title: \"x'") == {"title": "\"x'"}
        assert self._fm("aliases:\n  - 'x\"") == {"aliases": ["'x\""]}
        # Inline list starts with `'`, not `"`: a leading `"` is csv's own quote, not ours.
        assert self._fm("aliases: ['x\", Other]") == {"aliases": ["'x\"", "Other"]}

    def test_empty_items_are_dropped(self):
        assert self._fm("aliases:\n  - One\n  -\n  - Two") == {"aliases": ["One", "Two"]}

    def test_items_containing_a_colon_are_not_read_as_keys(self):
        # "- Note: A Subtitle" is an item, not a nested key — the dash decides.
        assert self._fm("aliases:\n  - Note: A Subtitle") == {"aliases": ["Note: A Subtitle"]}

    def test_a_flush_left_block_list_parses_to_a_list(self):
        # YAML permits "- item" at the parent key's own indentation; Obsidian-family tools write it.
        parsed = self._fm("tags:\n- foo\n- bar\ntitle: x")
        assert parsed == {"tags": ["foo", "bar"], "title": "x"}

    def test_a_flush_left_item_with_no_open_list_is_still_dropped(self):
        # #222's rule survives the regex broadening: no list open means the dash line is a stray.
        assert self._fm("title: x\n- foo") == {"title": "x"}

    def test_a_colon_bearing_flush_left_item_with_no_open_list_is_dropped(self):
        # The same stray with a colon in its text: the dash decides, so it is not a "- Note" key.
        assert self._fm("title: x\n- Note: Subtitle") == {"title": "x"}

    def test_a_blank_line_inside_a_list_does_not_truncate_it(self):
        # A blank line must not close the open list: the item after it still belongs to it.
        parsed = self._fm("aliases:\n  - One\n  - Two\n\n  - Three\ndate: X\n")
        assert parsed == {"aliases": ["One", "Two", "Three"], "date": "X"}

    def test_a_blank_line_between_two_block_lists_keeps_both_intact(self):
        parsed = self._fm("aliases:\n  - A\n\ntags:\n  - x\n  - y\n")
        assert parsed == {"aliases": ["A"], "tags": ["x", "y"]}

    def test_a_blank_line_then_a_scalar_key_still_closes_the_list(self):
        parsed = self._fm("aliases:\n  - A\n\ndate: 2026-07-25\n")
        assert parsed == {"aliases": ["A"], "date": "2026-07-25"}

    def test_a_block_list_survives_a_real_note(self, tmp_path):
        note = tmp_path / "n.md"
        note.write_text(
            "---\naliases:\n  - Mood Tracker\ntags:\n  - health\n---\n\nBody [[x]].\n",
            encoding="utf-8",
        )
        doc = parse_document(note, tmp_path)
        assert doc.frontmatter["aliases"] == ["Mood Tracker"]
        assert doc.frontmatter["tags"] == ["health"]
        assert "Body" in doc.text

    def test_comment_line_inside_a_block_list_does_not_end_it(self):
        # A full-line YAML comment is not structure: the item after it still belongs to the list.
        parsed = self._fm("aliases:\n  - One\n# a note to self\n  - Two\ndate: X\n")
        assert parsed == {"aliases": ["One", "Two"], "date": "X"}
        # An indented comment behaves the same.
        assert self._fm("aliases:\n  - One\n  # note\n  - Two") == {"aliases": ["One", "Two"]}

    def test_comment_line_with_a_colon_is_not_stored_as_a_key(self):
        assert self._fm("title: T\n# TODO: revisit\ndate: X") == {"title": "T", "date": "X"}
        parsed = self._fm("aliases:\n  - One\n# TODO: revisit\n  - Two")
        assert parsed == {"aliases": ["One", "Two"]}

    def test_a_hash_inside_a_value_is_not_a_comment(self):
        # Only a FULL-LINE comment is skipped. A `#` within a value stays untruncated, and
        # trailing inline comments are deliberately not handled.
        assert self._fm('color: "#ff0000"') == {"color": "#ff0000"}
        assert self._fm("tag: #project") == {"tag": "#project"}
        assert self._fm("tags: [#a, #b]") == {"tags": ["#a", "#b"]}
        assert self._fm("aliases:\n  - #project") == {"aliases": ["#project"]}


class TestNestedMappingFrontmatter:
    """`key:` followed by indented `subkey: value` lines (a nested YAML mapping) — see #264.

    A nested mapping is not a supported shape, so it must yield nothing. It used to fall through
    to the generic `key: value` branch, whose `partition` stripped the indent and promoted the
    subkey to a spurious TOP-LEVEL key, silently overwriting a real key of the same name.
    """

    def _fm(self, raw: str) -> dict:
        from graphmark.parse import _parse_frontmatter

        return _parse_frontmatter(raw)

    def test_nested_mapping_subkey_is_not_promoted(self):
        # Outer key stays "" (an unparseable block value, as today); a real top-level key after
        # the mapping still parses (folded companion assertion).
        parsed = self._fm("cssclasses:\n  wide: true\ntitle: Real")
        assert parsed == {"cssclasses": "", "title": "Real"}

    def test_every_subkey_of_a_nested_mapping_is_dropped(self):
        parsed = self._fm("cssclasses:\n  wide: true\n  narrow: false\ntitle: Real")
        assert parsed == {"cssclasses": "", "title": "Real"}

    def test_real_top_level_key_not_overwritten_by_nested_subkey(self):
        # Real key FIRST, nested subkey of the same name AFTER: the nested value used to win.
        parsed = self._fm("wide: real\ncssclasses:\n  wide: nested")
        assert parsed == {"wide": "real", "cssclasses": ""}

    def test_real_top_level_key_after_a_nested_subkey_of_the_same_name(self):
        # Nested subkey FIRST, real key AFTER: the real key must win, and `wide` must not be
        # present merely because of the nested line.
        parsed = self._fm("cssclasses:\n  wide: nested\nwide: real")
        assert parsed == {"cssclasses": "", "wide": "real"}

    def test_a_colon_bearing_stray_item_still_drops_with_no_list_open(self):
        # #222's construct: unaffected by this fix.
        parsed = self._fm("aliases:\n  - One\ndate: 2026-07-25\n  - Note: Subtitle")
        assert parsed == {"aliases": ["One"], "date": "2026-07-25"}

    def test_an_unindented_key_after_a_bare_key_is_still_a_key(self):
        assert self._fm("aliases:\ndate: 2026-07-25") == {"aliases": "", "date": "2026-07-25"}


class TestFrontmatterListParsing:
    """Inline lists (`key: [a, b]`) split naively on every comma, including commas embedded
    inside a double-quoted item. A note declaring `aliases: ["Smith, John", "Doe, Jane"]` meant
    two aliases but silently got four bogus, wrong ones fed into `build_aliases` — see #227.
    """

    def _fm(self, raw: str) -> dict:
        from graphmark.parse import _parse_frontmatter

        return _parse_frontmatter(raw)

    def test_quoted_comma_bearing_items_are_preserved(self):
        assert self._fm('aliases: ["Smith, John", "Doe, Jane"]') == {
            "aliases": ["Smith, John", "Doe, Jane"]
        }

    def test_unquoted_apostrophe_is_not_a_quote_delimiter(self):
        assert self._fm("aliases: [O'Brien, Smith]") == {"aliases": ["O'Brien", "Smith"]}

    def test_empty_inline_list_does_not_raise(self):
        assert self._fm("aliases: []") == {"aliases": []}

    def test_a_multiline_inline_list_is_excluded_not_corrupted(self):
        # A flow list wrapped across lines is unparseable here; the key is dropped rather than
        # stored as the truncated literal "[one," (and the continuation line is not a key).
        assert self._fm("tags: [one,\n  two]") == {}
        assert self._fm("tags: [one,\n  two]\ndate: 2026-07-25") == {"date": "2026-07-25"}

    def test_an_unterminated_inline_list_is_excluded(self):
        assert self._fm("tags: [one, two") == {}
        assert self._fm("tags: [one, two\ndate: 2026-07-25") == {"date": "2026-07-25"}


class TestFixtureFrontmatterUnchanged:
    def test_no_fixture_note_uses_a_block_list(self):
        # The parity argument for this change: fixture notes use inline/scalar frontmatter only,
        # so no expected.json can move. If this ever fails, re-check the oracles before shipping.
        import re

        block_key = re.compile(r"^[A-Za-z_][\w-]*:\s*$", re.MULTILINE)
        fixtures = Path(__file__).parent / "fixtures"
        offenders = []
        for note in fixtures.rglob("*.md"):
            raw = note.read_text(encoding="utf-8")
            if not raw.startswith("---"):
                continue
            end = raw.find("\n---", 3)
            if block_key.search(raw[3:end] if end != -1 else raw[3:]):
                offenders.append(str(note))
        assert offenders == []
