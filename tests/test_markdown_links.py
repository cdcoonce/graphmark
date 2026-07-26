"""Markdown-style `[text](note.md)` links, config-gated (#152).

The roadmap lists alternate link-syntax adapters under non-goals with a precise escape hatch — "the
pluggable interfaces exist so these _can_ be added on demand; do not build them speculatively." The
second corpus run supplied the demand: `lyz-code/blue-book`, 1120 notes, 11,198 markdown-style links
(99% targeting a real note), zero extracted edges.

Four decisions this encodes, all reversible in config:

1. **Selection** is `link_syntax = "wikilink" | "markdown" | "both"`, defaulting to `"wikilink"`.
   Every existing vault, every frozen fixture and the reference vault are byte-identical untouched.
2. **Resolution is relative to the linking note**, which is genuinely new: a markdown target is a
   path, not a name. Rather than change the `Resolver` protocol — which never receives the source
   note, and which the roadmap forbids redesigning — the target is normalized into a vault-relative
   path *before* diagnosis, where the existing path branch resolves it exactly.
3. **No new frozen fixture.** The oracle is wikilink-only and regenerating it is a human's call
   (Track B); these are hand-written assertions instead.
4. **A target that escapes the vault root is `missing`**, not resolved and not an error.
"""

from __future__ import annotations

from pathlib import Path

from graphmark.config import VaultConfig
from graphmark.graph import NormalizeResolver, VaultGraph
from graphmark.parse import MarkdownLinkExtractor, WikilinkExtractor


def _write(root: Path, rel: str, text: str = "") -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build(root: Path, **config_kwargs) -> VaultGraph:
    return VaultGraph.build(
        VaultConfig(root=root, **config_kwargs), WikilinkExtractor(), NormalizeResolver()
    )


class TestExtractor:
    def test_extracts_a_relative_target(self):
        assert MarkdownLinkExtractor().extract("[the note](other.md)") == ["other.md"]

    def test_keeps_the_target_not_the_display_text(self):
        assert MarkdownLinkExtractor().extract("[Some Title](a/b.md)") == ["a/b.md"]

    def test_drops_an_anchor(self):
        assert MarkdownLinkExtractor().extract("[x](note.md#Section)") == ["note.md"]

    def test_ignores_images_urls_and_non_markdown_targets(self):
        text = "![i](c.png) [u](https://x.com/a.md) [p](doc.pdf) [[Wiki]]"
        assert MarkdownLinkExtractor().extract(text) == []

    def test_ignores_code_spans_and_fences(self):
        assert MarkdownLinkExtractor().extract("`[a](n.md)`\n```\n[b](n.md)\n```\n") == []

    def test_decodes_percent_encoding(self):
        # Real markdown encodes spaces; the vault stores them literally.
        assert MarkdownLinkExtractor().extract("[x](my%20note.md)") == ["my note.md"]


class TestDefaultIsUnchanged:
    def test_markdown_links_are_ignored_by_default(self, tmp_path):
        _write(tmp_path, "a.md", "[one](b.md)\n")
        _write(tmp_path, "b.md")
        graph = _build(tmp_path)
        assert graph.out_links["a.md"] == set()
        assert sum(graph.link_counts.values()) == 0

    def test_wikilinks_still_work_in_markdown_mode_only_if_asked(self, tmp_path):
        _write(tmp_path, "a.md", "[[b]]\n")
        _write(tmp_path, "b.md")
        assert _build(tmp_path, link_syntax="markdown").out_links["a.md"] == set()
        assert _build(tmp_path, link_syntax="both").out_links["a.md"] == {"b.md"}


class TestRelativeResolution:
    def test_a_sibling_target_resolves(self, tmp_path):
        _write(tmp_path, "docs/a.md", "[one](b.md)\n")
        _write(tmp_path, "docs/b.md")
        assert _build(tmp_path, link_syntax="markdown").out_links["docs/a.md"] == {"docs/b.md"}

    def test_a_parent_relative_target_resolves(self, tmp_path):
        _write(tmp_path, "docs/deep/a.md", "[one](../other/b.md)\n")
        _write(tmp_path, "docs/other/b.md")
        graph = _build(tmp_path, link_syntax="markdown")
        assert graph.out_links["docs/deep/a.md"] == {"docs/other/b.md"}

    def test_an_explicit_dot_slash_resolves(self, tmp_path):
        _write(tmp_path, "docs/a.md", "[one](./b.md)\n")
        _write(tmp_path, "docs/b.md")
        assert _build(tmp_path, link_syntax="markdown").out_links["docs/a.md"] == {"docs/b.md"}

    def test_the_same_name_in_two_folders_does_not_collide(self, tmp_path):
        # The point of relative resolution: a bare name is NOT ambiguous here, because the
        # linking note's folder decides. Under wikilink rules this same pair is ambiguous.
        _write(tmp_path, "one/a.md", "[x](n.md)\n")
        _write(tmp_path, "one/n.md")
        _write(tmp_path, "two/n.md")
        graph = _build(tmp_path, link_syntax="markdown")
        assert graph.out_links["one/a.md"] == {"one/n.md"}
        assert graph.link_counts["ambiguous"] == 0

    def test_a_target_escaping_the_vault_is_missing(self, tmp_path):
        _write(tmp_path, "a.md", "[out](../outside.md)\n")
        graph = _build(tmp_path, link_syntax="markdown")
        assert graph.link_counts["missing"] == 1
        assert graph.out_links["a.md"] == set()

    def test_a_target_that_does_not_exist_is_missing(self, tmp_path):
        _write(tmp_path, "a.md", "[gone](nowhere.md)\n")
        assert _build(tmp_path, link_syntax="markdown").link_counts["missing"] == 1

    def test_a_self_link_is_not_an_edge(self, tmp_path):
        _write(tmp_path, "a.md", "[self](a.md)\n")
        graph = _build(tmp_path, link_syntax="markdown")
        assert graph.out_links["a.md"] == set()
        assert graph.link_counts["resolved"] == 1


class TestBothModes:
    def test_both_syntaxes_are_counted_and_conserved(self, tmp_path):
        _write(tmp_path, "a.md", "[[b]]\n[one](b.md)\n[gone](nope.md)\n")
        _write(tmp_path, "b.md")
        graph = _build(tmp_path, link_syntax="both")
        assert sum(graph.link_counts.values()) == 3
        assert graph.link_counts["resolved"] == 2
        assert graph.link_counts["missing"] == 1
        assert graph.out_links["a.md"] == {"b.md"}

    def test_the_unread_syntax_warning_is_silent_once_markdown_is_read(self, tmp_path, capsys):
        _write(tmp_path, "a.md", "[1](b.md)\n[2](b.md)\n[3](b.md)\n")
        _write(tmp_path, "b.md")
        _build(tmp_path, link_syntax="both")
        assert capsys.readouterr().err == ""


class TestConfig:
    def test_an_unknown_syntax_is_rejected(self, tmp_path):
        _write(tmp_path, "a.md")
        try:
            _build(tmp_path, link_syntax="logseq")
        except ValueError as e:
            assert "link_syntax" in str(e)
        else:
            raise AssertionError("an unknown link_syntax must fail loudly")

    def test_it_loads_from_toml(self, tmp_path):
        from graphmark.config import load_config

        cfg = tmp_path / "v.toml"
        cfg.write_text(f'root = "{tmp_path}"\nlink_syntax = "both"\n', encoding="utf-8")
        assert load_config(cfg).link_syntax == "both"
