"""Tests for parse.py: WikilinkExtractor and parse_document."""

from pathlib import Path

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
