"""Warn when the vault's links are in a syntax graphmark does not read (#151).

graphmark can report a confidently empty graph for a densely linked vault. Measured on
`lyz-code/blue-book`: 1120 notes, 11,198 markdown-style `[text](note.md)` links (99% of them
targeting a note that exists), and **zero** extracted edges. Every note an orphan, and `check` looks
nearly healthy — `max_unresolved_links` sees 38, because links that were never extracted are not
*unresolved*.

The conservation law from #124 cannot catch this: it sums over what the extractor produced, so a
syntax the extractor does not know is invisible to it by construction. The buckets balance perfectly
at 39 while 11,198 links sit outside the universe being counted.

The signal is deliberately relational, not calibrated — it fires only when the unread syntax
*outnumbers* the read one. No threshold to tune and no false-positive mode, in the same spirit as
#133's assertion.
"""

from __future__ import annotations

from pathlib import Path

from graphmark.config import VaultConfig
from graphmark.graph import NormalizeResolver, VaultGraph
from graphmark.parse import WikilinkExtractor, count_markdown_links


def _write(root: Path, rel: str, text: str = "") -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build(root: Path, **config_kwargs) -> VaultGraph:
    return VaultGraph.build(
        VaultConfig(root=root, **config_kwargs), WikilinkExtractor(), NormalizeResolver()
    )


class TestCounting:
    def test_counts_a_relative_markdown_link(self):
        assert count_markdown_links("see [the note](other.md) here") == 1

    def test_counts_a_path_and_an_anchor(self):
        assert count_markdown_links("[a](../deep/note.md) [b](note.md#Section)") == 2

    def test_ignores_absolute_urls(self):
        text = "[spec](https://example.com/docs/README.md) [m](mailto:x@y.md)"
        assert count_markdown_links(text) == 0

    def test_ignores_images_and_non_markdown_targets(self):
        assert count_markdown_links("![img](chart.png) [pdf](doc.pdf) [c](board.canvas)") == 0

    def test_ignores_wikilinks(self):
        assert count_markdown_links("[[Note]] and [[folder/Note.md]]") == 0

    def test_ignores_a_link_inside_a_code_fence(self):
        # Same exclusion the wikilink extractor applies; a documented example is not a link.
        assert count_markdown_links("```\n[a](note.md)\n```\n") == 0

    def test_ignores_a_link_inside_an_inline_code_span(self):
        assert count_markdown_links("`[a](note.md)`") == 0


class TestWarning:
    def test_warns_when_the_unread_syntax_outnumbers_the_read_one(self, tmp_path, capsys):
        _write(tmp_path, "a.md", "[one](b.md)\n[two](c.md)\n[three](b.md)\n[[b]]\n")
        _write(tmp_path, "b.md")
        _write(tmp_path, "c.md")
        _build(tmp_path)
        captured = capsys.readouterr()
        assert captured.out == "", "the JSON surface must stay pipeable"
        assert "3" in captured.err and "markdown" in captured.err.lower()
        assert captured.err.count("warning") == 1, "exactly one line, not one per note"

    def test_is_silent_when_wikilinks_dominate(self, tmp_path, capsys):
        # The reference vault's real ratio: a handful of markdown links against thousands of
        # wikilinks. This must never fire there.
        body = "[[b]]\n" * 20 + "[stray](b.md)\n"
        _write(tmp_path, "a.md", body)
        _write(tmp_path, "b.md")
        _build(tmp_path)
        assert capsys.readouterr().err == ""

    def test_is_silent_with_no_markdown_links_at_all(self, tmp_path, capsys):
        _write(tmp_path, "a.md", "[[b]]\n")
        _write(tmp_path, "b.md")
        _build(tmp_path)
        assert capsys.readouterr().err == ""

    def test_is_silent_on_an_empty_vault(self, tmp_path, capsys):
        _write(tmp_path, "a.md", "no links here\n")
        _build(tmp_path)
        assert capsys.readouterr().err == ""

    def test_an_equal_count_does_not_warn(self, tmp_path, capsys):
        # Strictly greater, so the signal cannot fire on a tie — deliberately conservative.
        _write(tmp_path, "a.md", "[[b]]\n[one](b.md)\n")
        _write(tmp_path, "b.md")
        _build(tmp_path)
        assert capsys.readouterr().err == ""


class TestNoBehaviorChange:
    def test_the_warning_changes_no_count_and_no_edge(self, tmp_path, capsys):
        _write(tmp_path, "a.md", "[one](b.md)\n[two](b.md)\n[[b]]\n")
        _write(tmp_path, "b.md")
        graph = _build(tmp_path)
        capsys.readouterr()
        assert graph.link_counts["resolved"] == 1
        assert sum(graph.link_counts.values()) == 1, "markdown links are counted nowhere"
        assert graph.out_links["a.md"] == {"b.md"}
