"""Path-qualified links normalize like bare ones (#146).

Bare resolution went through `_normalize` — NFC, lowercase, punctuation and symbols folded — while
path resolution went through `_fold_case`, which folds only case and Unicode form. So
`[[Q1 - Review]]` found `Q1 — Review.md` but `[[notes/Q1 - Review]]` did not: the same title was
reachable or not depending on whether the writer happened to qualify the link with a folder, which
is arbitrary from a user's point of view.

The fix compares **path components**, each normalized by the one function: the display's components
must be a suffix of the candidate's. That subsumes #136's boundary rule for free — a suffix over
lists cannot match mid-component — while letting every punctuation equivalence `_normalize` already
absorbs work in both branches.

The trap this must not fall into: `/` is structural. `[[a/b]]` must never reach `a-b.md`, even
though `a/b` and `a-b` normalize to the same characters once the separator is folded. Components
are normalized individually and the separator is never one of them, which keeps them apart.
"""

from __future__ import annotations

from pathlib import Path

from graphmark.config import VaultConfig
from graphmark.graph import NormalizeResolver, VaultGraph, candidates_for
from graphmark.parse import WikilinkExtractor


def _write(root: Path, rel: str, text: str = "") -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build(root: Path, **kw) -> VaultGraph:
    return VaultGraph.build(VaultConfig(root=root, **kw), WikilinkExtractor(), NormalizeResolver())


class TestSeparatorStaysStructural:
    """The trap. A `/` is a path boundary, never a character to fold."""

    def test_a_slash_display_does_not_reach_a_hyphen_file(self, tmp_path):
        _write(tmp_path, "a-b.md")
        _write(tmp_path, "src.md", "[[a/b]]")
        graph = _build(tmp_path)
        assert graph.unresolved == {"src.md": ["a/b"]}
        assert candidates_for("a/b", graph.catalog) == []

    def test_a_slash_display_does_not_reach_a_space_file(self, tmp_path):
        _write(tmp_path, "a b.md")
        _write(tmp_path, "src.md", "[[a/b]]")
        assert _build(tmp_path).unresolved == {"src.md": ["a/b"]}

    def test_a_hyphen_display_does_not_reach_a_nested_file(self, tmp_path):
        # The reverse direction: "a-b" is one name, not two components.
        _write(tmp_path, "a/b.md")
        _write(tmp_path, "src.md", "[[a-b]]")
        assert _build(tmp_path).unresolved == {"src.md": ["a-b"]}


class TestPunctuationFoldsWithinAComponent:
    def test_a_path_qualified_em_dash_title(self, tmp_path):
        _write(tmp_path, "notes/Q1 — Review.md")
        _write(tmp_path, "src.md", "[[notes/Q1 - Review]]")
        graph = _build(tmp_path)
        assert graph.unresolved == {}
        assert graph.out_links["src.md"] == {"notes/Q1 — Review.md"}

    def test_a_path_qualified_hyphen_vs_space(self, tmp_path):
        _write(tmp_path, "notes/oura pipeline.md")
        _write(tmp_path, "src.md", "[[notes/oura-pipeline]]")
        assert _build(tmp_path).unresolved == {}

    def test_the_folder_component_folds_too(self, tmp_path):
        _write(tmp_path, "my-notes/thing.md")
        _write(tmp_path, "src.md", "[[my notes/thing]]")
        assert _build(tmp_path).unresolved == {}

    def test_both_branches_now_agree(self, tmp_path):
        # The actual defect: the same title, reachable one way and not the other.
        _write(tmp_path, "notes/Q1 — Review.md")
        _write(tmp_path, "src.md", "[[Q1 - Review]]\n[[notes/Q1 - Review]]")
        graph = _build(tmp_path)
        assert graph.unresolved == {}
        assert graph.link_counts["resolved"] == 2


class TestBoundaryRuleSurvives:
    """#136's guarantee, now a consequence of comparing component lists."""

    def test_a_longer_folder_name_still_does_not_satisfy_a_shorter_one(self, tmp_path):
        _write(tmp_path, "homework/Tasks.md")
        _write(tmp_path, "src.md", "[[work/Tasks]]")
        assert _build(tmp_path).unresolved == {"src.md": ["work/Tasks"]}

    def test_any_depth_of_prefix_still_resolves(self, tmp_path):
        _write(tmp_path, "a/b/work/Tasks.md")
        _write(tmp_path, "src.md", "[[work/Tasks]]")
        assert _build(tmp_path).out_links["src.md"] == {"a/b/work/Tasks.md"}

    def test_a_whole_path_still_resolves(self, tmp_path):
        _write(tmp_path, "work/Tasks.md")
        _write(tmp_path, "src.md", "[[work/Tasks]]")
        assert _build(tmp_path).out_links["src.md"] == {"work/Tasks.md"}

    def test_a_genuine_collision_is_still_ambiguous(self, tmp_path):
        _write(tmp_path, "a/work/Tasks.md")
        _write(tmp_path, "b/work/Tasks.md")
        _write(tmp_path, "src.md", "[[work/Tasks]]")
        graph = _build(tmp_path)
        assert graph.link_counts["ambiguous"] == 1
        assert candidates_for("work/Tasks", graph.catalog) == [
            "a/work/Tasks.md",
            "b/work/Tasks.md",
        ]

    def test_case_and_unicode_form_still_fold(self, tmp_path):
        _write(tmp_path, "Work/Tasks.md")
        _write(tmp_path, "src.md", "[[work/tasks]]")
        assert _build(tmp_path).unresolved == {}


class TestMarkdownModeAgrees:
    def test_a_markdown_link_to_a_punctuation_variant_resolves(self, tmp_path):
        # Markdown targets are normalized to full vault-relative paths, so they take the same
        # component path — the fix must reach them too.
        _write(tmp_path, "notes/Q1 — Review.md")
        # Percent-encoded, because a bare space in a destination is not a link per CommonMark —
        # it needs <> or encoding. That also exercises the decode path.
        _write(tmp_path, "notes/src.md", "[x](Q1%20-%20Review.md)\n")
        graph = _build(tmp_path, link_syntax="markdown")
        assert graph.out_links["notes/src.md"] == {"notes/Q1 — Review.md"}


class TestDegenerate:
    def test_a_trailing_slash_names_nothing(self, tmp_path):
        _write(tmp_path, "a/b.md")
        assert candidates_for("a/", _build(tmp_path).catalog) == []

    def test_a_punctuation_only_component_names_nothing(self, tmp_path):
        _write(tmp_path, "a/b.md")
        assert candidates_for("a/--", _build(tmp_path).catalog) == []
