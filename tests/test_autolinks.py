"""The mkdocs-autolinks dialect: a bare markdown target resolves by name (#156).

A markdown link is a *relative path* — `[tdd](tdd.md)` from `docs/architecture/x.md` means
`docs/architecture/tdd.md` and nothing else. But the widely-used `mkdocs-autolinks` plugin resolves
a bare filename **anywhere in the tree**, so the same link reaches `docs/coding/tdd.md`. Measured on
`lyz-code/blue-book`, which runs that plugin: 5.8% of its links resolve strictly, 92.7% by name.

This is an explicit fourth `link_syntax` value, **not a fallback**. Trying a second rule when the
first fails is the shape of #136 — a rule that quietly produces an edge to a note the link does not
name — and the 1.5% that match neither dialect show a fallback would not even be complete. The vault
owner states which renderer they use, exactly as they already state their scope.

A bare name goes to the *existing* wikilink rule, so ambiguity is refused the same way it
always was: no dialect may invent a resolution.
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


def _build(root: Path, **kw) -> VaultGraph:
    return VaultGraph.build(VaultConfig(root=root, **kw), WikilinkExtractor(), NormalizeResolver())


class TestBareTargetsResolveByName:
    def test_a_bare_target_reaches_a_note_elsewhere_in_the_tree(self, tmp_path):
        # blue-book's shape: [tdd](tdd.md) from docs/architecture/ reaching docs/coding/tdd.md.
        _write(tmp_path, "docs/coding/tdd.md")
        _write(tmp_path, "docs/architecture/x.md", "[tdd](tdd.md)\n")
        graph = _build(tmp_path, link_syntax="markdown-autolinks")
        assert graph.out_links["docs/architecture/x.md"] == {"docs/coding/tdd.md"}
        assert graph.link_counts["missing"] == 0

    def test_strict_markdown_still_reports_that_link_missing(self, tmp_path):
        _write(tmp_path, "docs/coding/tdd.md")
        _write(tmp_path, "docs/architecture/x.md", "[tdd](tdd.md)\n")
        assert _build(tmp_path, link_syntax="markdown").link_counts["missing"] == 1

    def test_a_sibling_target_still_resolves(self, tmp_path):
        _write(tmp_path, "docs/b.md")
        _write(tmp_path, "docs/a.md", "[b](b.md)\n")
        assert _build(tmp_path, link_syntax="markdown-autolinks").out_links["docs/a.md"] == {
            "docs/b.md"
        }

    def test_the_name_normalizes_like_any_other(self, tmp_path):
        _write(tmp_path, "docs/coding/Q1 — Review.md")
        _write(tmp_path, "x.md", "[q](Q1%20-%20Review.md)\n")
        assert _build(tmp_path, link_syntax="markdown-autolinks").unresolved == {}


class TestAmbiguityIsStillRefused:
    def test_a_name_claimed_by_two_notes_is_ambiguous(self, tmp_path):
        # The rule this dialect must not break: no dialect may invent a resolution.
        _write(tmp_path, "one/note.md")
        _write(tmp_path, "two/note.md")
        _write(tmp_path, "x.md", "[n](note.md)\n")
        graph = _build(tmp_path, link_syntax="markdown-autolinks")
        assert graph.link_counts["ambiguous"] == 1
        assert graph.out_links["x.md"] == set()

    def test_a_name_that_exists_nowhere_is_missing(self, tmp_path):
        _write(tmp_path, "x.md", "[gone](nowhere.md)\n")
        assert _build(tmp_path, link_syntax="markdown-autolinks").link_counts["missing"] == 1


class TestPathQualifiedTargetsStayRelative:
    def test_a_target_with_a_slash_uses_the_relative_rule(self, tmp_path):
        # Only *bare* names get the plugin's behavior; a qualified target still means what it says.
        _write(tmp_path, "docs/deep/other/b.md")
        _write(tmp_path, "docs/deep/a.md", "[b](other/b.md)\n")
        assert _build(tmp_path, link_syntax="markdown-autolinks").out_links["docs/deep/a.md"] == {
            "docs/deep/other/b.md"
        }

    def test_a_qualified_target_that_is_wrong_is_not_rescued_by_name(self, tmp_path):
        # The anti-fallback assertion: "elsewhere/b.md" names no note here, and the fact that a
        # b.md exists somewhere must NOT rescue it. That rescue is exactly the #136 shape.
        _write(tmp_path, "docs/coding/b.md")
        _write(tmp_path, "docs/a.md", "[b](elsewhere/b.md)\n")
        graph = _build(tmp_path, link_syntax="markdown-autolinks")
        assert graph.link_counts["missing"] == 1
        assert graph.out_links["docs/a.md"] == set()

    def test_a_parent_relative_target_still_resolves(self, tmp_path):
        _write(tmp_path, "docs/other/b.md")
        _write(tmp_path, "docs/deep/a.md", "[b](../other/b.md)\n")
        assert _build(tmp_path, link_syntax="markdown-autolinks").out_links["docs/deep/a.md"] == {
            "docs/other/b.md"
        }


class TestOtherModesUnchanged:
    def test_wikilinks_are_not_read_in_this_mode(self, tmp_path):
        _write(tmp_path, "b.md")
        _write(tmp_path, "a.md", "[[b]]\n")
        assert _build(tmp_path, link_syntax="markdown-autolinks").out_links["a.md"] == set()

    def test_the_default_is_still_wikilink(self, tmp_path):
        _write(tmp_path, "b.md")
        _write(tmp_path, "a.md", "[b](b.md)\n[[b]]\n")
        graph = _build(tmp_path)
        assert graph.link_counts["resolved"] == 1


class TestConfig:
    def test_it_is_an_accepted_syntax(self, tmp_path):
        from graphmark.config import LINK_SYNTAXES

        assert "markdown-autolinks" in LINK_SYNTAXES

    def test_it_loads_from_toml(self, tmp_path):
        from graphmark.config import load_config

        cfg = tmp_path / "v.toml"
        cfg.write_text(
            f'root = "{tmp_path}"\nlink_syntax = "markdown-autolinks"\n', encoding="utf-8"
        )
        assert load_config(cfg).link_syntax == "markdown-autolinks"
