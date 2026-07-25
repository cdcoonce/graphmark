"""`non-note-file` must not swallow a genuinely broken link (#138).

`_targets_non_note_file` treated any trailing `.` + 1-10 alphanumerics as a file extension, so a
broken link to a note whose title ends in a decimal was silently suppressed instead of reported.
`.5` satisfies the pattern as readily as `.md` does.

This is the first class found that *deflates* `check`'s flagship number rather than inflating it,
which is strictly worse for a gate: an undercount is invisible by construction and reads as health.

The separating rule is that a real extension contains a letter. `.5` and `.61850` differ only in
length, so no length bound can tell them apart.
"""

from __future__ import annotations

from pathlib import Path

from graphmark.config import VaultConfig
from graphmark.graph import NormalizeResolver, VaultGraph
from graphmark.parse import WikilinkExtractor


def _write(root: Path, rel: str, text: str = "") -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build(root: Path, **config_kwargs) -> VaultGraph:
    return VaultGraph.build(
        VaultConfig(root=root, **config_kwargs), WikilinkExtractor(), NormalizeResolver()
    )


class TestNumberedTitlesAreReported:
    def test_a_decimal_suffix_is_a_missing_note_not_a_file(self, tmp_path):
        _write(tmp_path, "src.md", "[[Meeting 3.5]]")
        graph = _build(tmp_path)
        assert graph.link_counts["missing"] == 1
        assert graph.link_counts["non-note-file"] == 0
        assert graph.unresolved == {"src.md": ["Meeting 3.5"]}

    def test_a_long_all_digit_suffix_is_still_a_note(self, tmp_path):
        # ".61850" and ".5" differ only in length — a length bound cannot separate them.
        _write(tmp_path, "src.md", "[[Standard IEC.61850]]")
        assert _build(tmp_path).link_counts["missing"] == 1

    def test_a_version_suffix_is_a_note(self, tmp_path):
        _write(tmp_path, "src.md", "[[Phase 2.1]] [[Spec v0.9]] [[Budget FY26.2]]")
        assert _build(tmp_path).link_counts["missing"] == 3


class TestRealExtensionsStillSuppressed:
    def test_canvas_base_and_images(self, tmp_path):
        _write(tmp_path, "src.md", "[[Board.canvas]] [[Archive.base]] [[chart.png]] [[doc.pdf]]")
        graph = _build(tmp_path)
        assert graph.link_counts["non-note-file"] == 4
        assert graph.unresolved == {}

    def test_an_aliased_non_note_target(self, tmp_path):
        # The vault's real shape: [[Decisions.base|Decisions]].
        _write(tmp_path, "src.md", "[[Decisions.base|Decisions]]")
        assert _build(tmp_path).link_counts["non-note-file"] == 1

    def test_a_mixed_alphanumeric_extension_is_still_a_file(self, tmp_path):
        _write(tmp_path, "src.md", "[[archive.7z]] [[track.mp3]] [[video.mp4]]")
        assert _build(tmp_path).link_counts["non-note-file"] == 3


class TestResolverStillWinsFirst:
    def test_a_real_note_with_a_dotted_stem_resolves(self, tmp_path):
        # The guard `_targets_non_note_file`'s docstring already claims: the resolver runs first, so
        # a note that genuinely resolves is never suppressed. Asserted rather than assumed.
        _write(tmp_path, "report.v2.md")
        _write(tmp_path, "src.md", "[[report.v2]]")
        graph = _build(tmp_path)
        assert graph.link_counts["resolved"] == 1
        assert graph.out_links["src.md"] == {"report.v2.md"}

    def test_a_real_note_named_with_a_decimal_resolves(self, tmp_path):
        _write(tmp_path, "Meeting 3.5.md")
        _write(tmp_path, "src.md", "[[Meeting 3.5]]")
        assert _build(tmp_path).out_links["src.md"] == {"Meeting 3.5.md"}


class TestConservation:
    def test_every_display_still_lands_in_exactly_one_bucket(self, tmp_path):
        _write(tmp_path, "src.md", "[[Meeting 3.5]] [[Board.canvas]] [[#Heading]] [[Gone]]")
        graph = _build(tmp_path)
        assert sum(graph.link_counts.values()) == 4
