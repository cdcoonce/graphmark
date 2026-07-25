"""Path-suffix resolution must match on path-component boundaries (#136).

`[[folder/note]]` is resolved by finding the rel_path that *ends with* `folder/note.md`. That test
was a raw string suffix, so `homework/Tasks.md` satisfied `[[work/Tasks]]` — the character before
the match was never required to be a separator.

This is the first defect class in this package that fabricates an **edge** rather than moving a
link between reported buckets. A wrong edge is invisible: the link counts `resolved`, so no bucket
looks implausible, and every downstream metric (orphans, hubs, clusters, bridges, siloed_notes,
PageRank) reads a graph that does not describe the vault. The mirror case is just as bad — when
both `work/Tasks.md` and `homework/Tasks.md` exist the spurious second match makes the resolver
decline, turning a *correct* link into a reported break.

`candidates_for` mirrors the resolver's matching and is exercised alongside it here: the ambiguity
set a consumer is shown must never contain a path the resolver would not have considered.
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


def _build(root: Path, **config_kwargs) -> VaultGraph:
    return VaultGraph.build(
        VaultConfig(root=root, **config_kwargs), WikilinkExtractor(), NormalizeResolver()
    )


class TestFolderBoundary:
    def test_a_longer_folder_name_does_not_satisfy_a_shorter_one(self, tmp_path):
        # There is no work/ folder in this vault, so the link is broken. Before #136 it silently
        # produced an edge to homework/Tasks.md.
        _write(tmp_path, "homework/Tasks.md")
        _write(tmp_path, "src.md", "[[work/Tasks]]")
        graph = _build(tmp_path)
        assert graph.out_links["src.md"] == set()
        assert graph.unresolved == {"src.md": ["work/Tasks"]}

    def test_the_real_folder_still_wins_when_both_exist(self, tmp_path):
        # The mirror failure: the spurious homework/ match made the match list length 2, the
        # resolver declined, and a correct link was reported ambiguous.
        _write(tmp_path, "work/Tasks.md")
        _write(tmp_path, "homework/Tasks.md")
        _write(tmp_path, "src.md", "[[work/Tasks]]")
        graph = _build(tmp_path)
        assert graph.out_links["src.md"] == {"work/Tasks.md"}
        assert graph.unresolved == {}

    def test_a_longer_stem_does_not_satisfy_the_note_part(self, tmp_path):
        # Same missing boundary one component to the right: "a/b.md" must not be matched by
        # "dir/xa/b.md" NOR by a file whose stem merely ends in the target's.
        _write(tmp_path, "notes/my-tasks.md")
        _write(tmp_path, "src.md", "[[notes/tasks]]")
        graph = _build(tmp_path)
        assert graph.unresolved == {"src.md": ["notes/tasks"]}


class TestStillResolves:
    def test_any_depth_of_prefix_above_the_named_folder(self, tmp_path):
        _write(tmp_path, "a/b/work/Tasks.md")
        _write(tmp_path, "src.md", "[[work/Tasks]]")
        assert _build(tmp_path).out_links["src.md"] == {"a/b/work/Tasks.md"}

    def test_a_whole_path_match_at_the_root(self, tmp_path):
        # The match is the entire rel_path — there is no preceding "/" to require.
        _write(tmp_path, "work/Tasks.md")
        _write(tmp_path, "src.md", "[[work/Tasks]]")
        assert _build(tmp_path).out_links["src.md"] == {"work/Tasks.md"}

    def test_a_fully_qualified_path_from_the_vault_root(self, tmp_path):
        _write(tmp_path, "a/b/work/Tasks.md")
        _write(tmp_path, "src.md", "[[a/b/work/Tasks]]")
        assert _build(tmp_path).out_links["src.md"] == {"a/b/work/Tasks.md"}

    def test_case_insensitivity_survives(self, tmp_path):
        _write(tmp_path, "Work/Tasks.md")
        _write(tmp_path, "src.md", "[[work/tasks]]")
        assert _build(tmp_path).out_links["src.md"] == {"Work/Tasks.md"}

    def test_a_genuine_collision_is_still_ambiguous(self, tmp_path):
        _write(tmp_path, "a/work/Tasks.md")
        _write(tmp_path, "b/work/Tasks.md")
        _write(tmp_path, "src.md", "[[work/Tasks]]")
        graph = _build(tmp_path)
        assert graph.unresolved == {"src.md": ["work/Tasks"]}
        assert graph.link_counts["ambiguous"] == 1


class TestCandidatesAgree:
    """candidates_for is the ambiguity set a consumer is shown; it must see exactly what the
    resolver saw. Two matchers that disagree is the drift this package removed from its consumer."""

    def test_a_non_boundary_path_is_not_offered_as_a_candidate(self, tmp_path):
        _write(tmp_path, "homework/Tasks.md")
        _write(tmp_path, "src.md", "[[work/Tasks]]")
        catalog = _build(tmp_path).catalog
        assert candidates_for("work/Tasks", catalog) == []

    def test_boundary_matches_are_still_offered(self, tmp_path):
        _write(tmp_path, "a/work/Tasks.md")
        _write(tmp_path, "b/work/Tasks.md")
        _write(tmp_path, "homework/Tasks.md")
        catalog = _build(tmp_path).catalog
        assert candidates_for("work/Tasks", catalog) == ["a/work/Tasks.md", "b/work/Tasks.md"]
