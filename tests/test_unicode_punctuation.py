"""Punctuation folding must cover non-ASCII marks (#139).

`_normalize` folded punctuation with a table built from `string.punctuation`, which is **ASCII
only**. Every non-ASCII punctuation mark survived normalization and then had to be typed
byte-for-byte: an em-dash title was unreachable from a typed hyphen, a curly apostrophe from a
straight one, `…` from `...`. The catalog key literally retained the mark while an ASCII-typed
display normalized it away, so the two could never meet.

The sibling of #123 in the same function — that one flattened Unicode *form*, this one flattens
Unicode *punctuation*. Ordering matters: NFC composition runs first, so a decomposed `é` becomes a
single letter rather than a letter plus a combining mark that this fold must not touch.
"""

from __future__ import annotations

import unicodedata
from pathlib import Path

from graphmark.config import VaultConfig
from graphmark.graph import NormalizeResolver, VaultGraph, _normalize
from graphmark.parse import WikilinkExtractor


def _write(root: Path, rel: str, text: str = "") -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build(root: Path, **config_kwargs) -> VaultGraph:
    return VaultGraph.build(
        VaultConfig(root=root, **config_kwargs), WikilinkExtractor(), NormalizeResolver()
    )


class TestFoldsNonAsciiPunctuation:
    def test_em_dash_folds_like_a_hyphen(self):
        assert _normalize("Q1 — Review") == _normalize("Q1 - Review") == "q1 review"

    def test_en_dash_folds_like_a_hyphen(self):
        assert _normalize("2026–2027 Plan") == _normalize("2026-2027 Plan")

    def test_curly_apostrophe_folds_like_a_straight_one(self):
        # macOS smart substitution produces the curly form in a title but not in typed link text.
        assert _normalize("Charles’ Notes") == _normalize("Charles' Notes")

    def test_curly_quotes_fold_like_straight_ones(self):
        assert _normalize("“Quoted” Note") == _normalize('"Quoted" Note')

    def test_ellipsis_folds_like_three_dots(self):
        assert _normalize("And so on…") == _normalize("And so on...")

    def test_a_symbol_folds_too(self):
        # Unicode category S, not P — arrows and math signs turn up in real note titles.
        assert _normalize("Trino → Snowflake") == _normalize("Trino - Snowflake")


class TestResolution:
    def test_an_em_dash_title_resolves_from_a_typed_hyphen(self, tmp_path):
        _write(tmp_path, "Q1 — Review.md")
        _write(tmp_path, "src.md", "[[Q1 - Review]]")
        graph = _build(tmp_path)
        assert graph.unresolved == {}
        assert graph.out_links["src.md"] == {"Q1 — Review.md"}

    def test_the_reverse_direction_resolves(self, tmp_path):
        _write(tmp_path, "Q1 - Review.md")
        _write(tmp_path, "src.md", "[[Q1 — Review]]")
        assert _build(tmp_path).unresolved == {}

    def test_an_alias_folds_identically(self, tmp_path):
        _write(tmp_path, "Target.md", "---\naliases: [Q1 — Review]\n---\nbody\n")
        _write(tmp_path, "src.md", "[[Q1 - Review]]")
        graph = _build(tmp_path)
        assert graph.out_links["src.md"] == {"Target.md"}

    def test_a_path_qualified_link_still_resolves(self, tmp_path):
        # Path-suffix matching folds case and form but NOT punctuation — a "/" is structural, and
        # folding punctuation there would make "a/b" match "a-b.md". Assert it keeps working.
        _write(tmp_path, "notes/Q1 Review.md")
        _write(tmp_path, "src.md", "[[notes/Q1 Review]]")
        assert _build(tmp_path).unresolved == {}


class TestCombiningMarksSurvive:
    """#123's behavior must survive: NFC runs first, so nothing decomposed reaches this fold."""

    def test_an_accent_is_not_stripped(self):
        assert _normalize("Café") == "café"

    def test_both_unicode_forms_still_agree(self):
        nfd = unicodedata.normalize("NFD", "Café")
        assert _normalize(nfd) == _normalize("Café") == "café"

    def test_a_decomposed_title_still_resolves(self, tmp_path):
        _write(tmp_path, unicodedata.normalize("NFD", "Café") + ".md")
        _write(tmp_path, "src.md", "[[Café]]")
        assert _build(tmp_path).unresolved == {}

    def test_non_latin_scripts_are_untouched(self):
        assert _normalize("日本語ノート") == "日本語ノート"
        assert _normalize("Привет Мир") == "привет мир"


class TestUnaffected:
    def test_pure_ascii_is_byte_identical(self):
        assert _normalize("Jordan Ellis") == "jordan ellis"
        assert _normalize("oura-pipeline") == "oura pipeline"
        assert _normalize("v1.2 release notes") == "v1 2 release notes"
        assert _normalize("[[Note]]|alias#anchor") == "note alias anchor"

    def test_a_display_of_only_punctuation_still_yields_an_empty_key(self):
        assert _normalize("—…→") == ""
