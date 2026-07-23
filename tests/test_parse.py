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

    def test_invalid_utf8_does_not_raise(self, tmp_path):
        note = tmp_path / "bad.md"
        note.write_bytes(b"# Bad note\n\nSome \xff\xfe invalid bytes and [[link]].")
        doc = parse_document(note, tmp_path)
        assert doc.rel_path == "bad.md"
        assert "[[link]]" in doc.text

    def test_invalid_utf8_emits_stderr_warning(self, tmp_path, capsys):
        note = tmp_path / "bad.md"
        note.write_bytes(b"# Bad note\n\n\xff\xfe invalid bytes.")
        parse_document(note, tmp_path)
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "graphmark: warning: bad.md: invalid UTF-8, decoded with replacement" in captured.err

    def test_valid_utf8_emits_no_warning(self, tmp_path, capsys):
        note = tmp_path / "plain.md"
        note.write_text("# Plain\n\nSome [[link]] here.")
        parse_document(note, tmp_path)
        captured = capsys.readouterr()
        assert captured.err == ""

    def test_crlf_frontmatter_still_parsed(self, tmp_path):
        note = tmp_path / "crlf.md"
        note.write_bytes(b"---\r\ndate: 2026-07-23\r\n---\r\nBody with [[link]].")
        doc = parse_document(note, tmp_path)
        assert doc.frontmatter == {"date": "2026-07-23"}
        assert not doc.text.lstrip().startswith("---")
        assert "[[link]]" in doc.text
