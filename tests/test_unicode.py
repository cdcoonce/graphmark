"""`_normalize` must be Unicode-form-agnostic (#123).

macOS's HFS+/APFS store filenames decomposed (**NFD**): `é` is `e` + U+0301. Text typed in Obsidian,
or written by almost any editor, is composed (**NFC**): a single U+00E9. `_normalize` lowercased,
folded punctuation and collapsed whitespace, but never normalized Unicode form — so the two strings
never compared equal and an accented note title was a phantom broken link. Obsidian resolves it.

Every filename and every link display goes through `_normalize`, so normalizing there fixes note
names, path-suffix matching and alias keys at once, and the two sides can never disagree about which
form they are in.

The tests write genuinely NFD bytes rather than assuming what the filesystem does with them: APFS
preserves what it is given, HFS+ did not, and a test relying on either is testing the filesystem.
"""

from __future__ import annotations

import unicodedata
from pathlib import Path

from graphmark.config import VaultConfig
from graphmark.graph import NormalizeResolver, VaultGraph, _fold_case, _normalize
from graphmark.parse import WikilinkExtractor

NFC = "Café"
NFD = unicodedata.normalize("NFD", NFC)


def _write(root: Path, rel: str, text: str = "") -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build(root: Path, **config_kwargs) -> VaultGraph:
    return VaultGraph.build(
        VaultConfig(root=root, **config_kwargs), WikilinkExtractor(), NormalizeResolver()
    )


def test_the_two_forms_are_genuinely_different_strings():
    # Guards the rest of the module: if this ever passes trivially the tests below prove nothing.
    assert NFC != NFD
    assert len(NFD) == len(NFC) + 1


class TestNormalize:
    def test_both_forms_produce_the_same_key(self):
        assert _normalize(NFD) == _normalize(NFC)

    def test_the_key_is_composed(self):
        assert _normalize(NFD) == unicodedata.normalize("NFC", _normalize(NFD))


class TestResolution:
    def test_an_nfd_filename_resolves_from_an_nfc_link(self, tmp_path):
        _write(tmp_path, f"{NFD}.md")
        _write(tmp_path, "src.md", f"[[{NFC}]]")
        graph = _build(tmp_path)
        assert graph.unresolved == {}
        assert len(graph.out_links["src.md"]) == 1

    def test_an_nfc_filename_resolves_from_an_nfd_link(self, tmp_path):
        _write(tmp_path, f"{NFC}.md")
        _write(tmp_path, "src.md", f"[[{NFD}]]")
        graph = _build(tmp_path)
        assert graph.unresolved == {}
        assert len(graph.out_links["src.md"]) == 1

    def test_a_path_qualified_link_normalizes_identically(self, tmp_path):
        _write(tmp_path, f"{NFD}/note.md")
        _write(tmp_path, "src.md", f"[[{NFC}/note]]")
        assert _build(tmp_path).unresolved == {}

    def test_an_alias_normalizes_identically(self, tmp_path):
        _write(tmp_path, "Target.md", f"---\naliases: [{NFD}]\n---\nbody\n")
        _write(tmp_path, "src.md", f"[[{NFC}]]")
        graph = _build(tmp_path)
        assert graph.unresolved == {}
        assert graph.out_links["src.md"] == {"Target.md"}

    def test_two_notes_differing_only_in_form_are_ambiguous(self, tmp_path):
        # They name the same thing to a human and to Obsidian's switcher, so refusing to pick is
        # the honest answer — not silently resolving to whichever the walk saw first.
        _write(tmp_path, f"a/{NFD}.md")
        _write(tmp_path, f"b/{NFC}.md")
        _write(tmp_path, "src.md", f"[[{NFC}]]")
        graph = _build(tmp_path)
        assert graph.link_counts["ambiguous"] == 1


class TestUnaffected:
    def test_pure_ascii_is_byte_identical(self):
        assert _normalize("Jordan Ellis") == "jordan ellis"
        assert _normalize("oura-pipeline") == "oura pipeline"

    def test_a_character_with_no_decomposition_is_untouched_by_composition(self):
        # The reference vault's only non-ASCII filenames are em-dashes, which have no
        # decomposition — which is exactly why this defect stayed invisible there. Asserted on
        # _fold_case, the composition step: #139 later folds the em-dash away as punctuation, and
        # asserting on _normalize would conflate the two.
        assert _fold_case("Q1 — Review") == "q1 — review"
