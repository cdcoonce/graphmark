"""A UTF-8 BOM must not defeat frontmatter parsing (#137).

`_FM_RE` is anchored with `.match`, and decoding leaves `U+FEFF` at index 0, so a BOM'd note has no
frontmatter as far as graphmark is concerned. One cause, two opposite symptoms:

* its `aliases:` never register, so links written against them are phantom breaks — #119's class,
  reintroduced through the parser;
* its frontmatter wikilinks stay in the body and become phantom edges — the exact failure `_FM_RE`'s
  own docstring says it exists to prevent. That regex was hardened for CRLF and for a block ending
  at EOF, but not for the byte that can precede the block.

The reference vault has no BOM'd notes. A vault synced from a Windows machine ordinarily does.
"""

from __future__ import annotations

from pathlib import Path

from graphmark.config import VaultConfig
from graphmark.graph import NormalizeResolver, VaultGraph
from graphmark.parse import WikilinkExtractor, parse_document

BOM = "﻿"


def _write_bytes(root: Path, rel: str, data: bytes) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _write(root: Path, rel: str, text: str = "") -> Path:
    return _write_bytes(root, rel, text.encode("utf-8"))


def _build(root: Path, **config_kwargs) -> VaultGraph:
    return VaultGraph.build(
        VaultConfig(root=root, **config_kwargs), WikilinkExtractor(), NormalizeResolver()
    )


class TestFrontmatterSplits:
    def test_a_bom_note_still_parses_its_frontmatter(self, tmp_path):
        path = _write(tmp_path, "a.md", f"{BOM}---\ntitle: A\n---\nbody\n")
        doc = parse_document(path, tmp_path)
        assert doc.frontmatter == {"title": "A"}
        assert doc.text == "body\n"

    def test_the_bom_never_reaches_the_body(self, tmp_path):
        # A BOM left in the text would ride along in an extracted display and in every downstream
        # normalization, so it has to be gone before the frontmatter split, not merely after it.
        path = _write(tmp_path, "a.md", f"{BOM}body [[Note]]\n")
        doc = parse_document(path, tmp_path)
        assert BOM not in doc.text
        assert WikilinkExtractor().extract(doc.text) == ["Note"]

    def test_an_interior_zero_width_no_break_space_is_content(self, tmp_path):
        # U+FEFF is only a byte-order mark at position 0; elsewhere it is legitimate text.
        path = _write(tmp_path, "a.md", f"before{BOM}after\n")
        assert parse_document(path, tmp_path).text == f"before{BOM}after\n"

    def test_a_bom_survives_the_replacement_decode_path(self, tmp_path):
        # Invalid UTF-8 falls back to errors="replace"; the BOM must still be stripped there.
        path = _write_bytes(tmp_path, "a.md", BOM.encode("utf-8") + b"---\ntitle: A\n---\n\xff\n")
        doc = parse_document(path, tmp_path)
        assert doc.frontmatter == {"title": "A"}
        assert not doc.text.startswith(BOM)


class TestGraphEffects:
    def test_a_bom_note_s_aliases_still_resolve(self, tmp_path):
        _write(tmp_path, "Target.md", f"{BOM}---\naliases: [TGT]\n---\nbody\n")
        _write(tmp_path, "src.md", "[[TGT]]")
        graph = _build(tmp_path)
        assert graph.aliases == {"tgt": "Target.md"}
        assert graph.unresolved == {}
        assert graph.out_links["src.md"] == {"Target.md"}

    def test_a_bom_note_s_frontmatter_links_are_not_edges(self, tmp_path):
        _write(tmp_path, "a.md", f'{BOM}---\nup: "[[Ghost]]"\n---\nbody\n')
        _write(tmp_path, "Ghost.md", "")
        graph = _build(tmp_path)
        assert graph.out_links["a.md"] == set()
        assert graph.link_counts["resolved"] == 0


class TestUnaffected:
    def test_a_bom_free_note_is_byte_identical(self, tmp_path):
        path = _write(tmp_path, "a.md", "---\ntitle: A\n---\nbody [[Note]]\n")
        doc = parse_document(path, tmp_path)
        assert doc.frontmatter == {"title": "A"}
        assert doc.text == "body [[Note]]\n"

    def test_a_bom_with_no_frontmatter_leaves_the_body_intact(self, tmp_path):
        path = _write(tmp_path, "a.md", f"{BOM}# Heading\n")
        assert parse_document(path, tmp_path).text == "# Heading\n"
