"""Tests for parse.py: WikilinkExtractor and parse_document."""

from pathlib import Path

from graphmark.model import Document
from graphmark.parse import WikilinkExtractor, parse_document

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
