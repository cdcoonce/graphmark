"""Tests for VaultGraph.build's file-selection filters: excluded_dirs and rules_files.

Both filters were previously mutation-dead: every fixture config sets excluded_dirs=[".git"]
but no fixture vault holds a note under an excluded dir, and no fixture vault contains a rules
file — so deleting either filter left the whole suite green. These build real vaults under
tmp_path (no frozen-fixture edits) and pin the semantics the live consumer depends on daily.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from graphmark.config import VaultConfig
from graphmark.graph import NormalizeResolver, VaultGraph
from graphmark.parse import WikilinkExtractor


def _write(root: Path, rel: str, text: str = "") -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build(root: Path, **config_kwargs) -> VaultGraph:
    return VaultGraph.build(
        VaultConfig(root=root, **config_kwargs),
        WikilinkExtractor(),
        NormalizeResolver(),
    )


class TestExcludedDirs:
    def test_note_in_excluded_dir_is_absent_from_nodes(self, tmp_path):
        _write(tmp_path, "keep.md", "A kept note.\n")
        _write(tmp_path, "archive/old.md", "An archived note.\n")
        graph = _build(tmp_path, excluded_dirs=["archive"])
        assert set(graph.nodes) == {"keep.md"}

    def test_excluded_note_contributes_no_back_edge(self, tmp_path):
        # Proves the note is gone from the GRAPH, not merely from the node list: its outgoing
        # link must not appear as a back-link on the in-scope target.
        _write(tmp_path, "keep.md", "A kept note.\n")
        _write(tmp_path, "archive/old.md", "Links out to [[keep]].\n")
        graph = _build(tmp_path, excluded_dirs=["archive"])
        assert graph.back_links["keep.md"] == set()
        assert "archive/old.md" not in graph.out_links

    def test_excluded_dir_matches_at_any_depth(self, tmp_path):
        _write(tmp_path, "keep.md", "A kept note.\n")
        _write(tmp_path, "docs/archive/deep.md", "Buried in an excluded dir.\n")
        graph = _build(tmp_path, excluded_dirs=["archive"])
        assert set(graph.nodes) == {"keep.md"}

    def test_multiple_excluded_dirs_all_apply(self, tmp_path):
        _write(tmp_path, "keep.md", "")
        _write(tmp_path, "archive/a.md", "")
        _write(tmp_path, "tmp/b.md", "")
        graph = _build(tmp_path, excluded_dirs=["archive", "tmp"])
        assert set(graph.nodes) == {"keep.md"}

    def test_excluded_dirs_are_directories_only_not_filenames(self, tmp_path):
        # Pins the rel_parts[:-1] slice: only the DIRECTORY components are tested against
        # excluded_dirs, so a FILE whose name matches an entry is still part of the vault.
        _write(tmp_path, "archive.md", "A note that merely shares the name.\n")
        _write(tmp_path, "archive/real.md", "Actually inside the excluded dir.\n")
        graph = _build(tmp_path, excluded_dirs=["archive.md", "archive"])
        assert set(graph.nodes) == {"archive.md"}

    def test_no_excluded_dirs_keeps_everything(self, tmp_path):
        _write(tmp_path, "keep.md", "")
        _write(tmp_path, "archive/old.md", "")
        graph = _build(tmp_path)
        assert set(graph.nodes) == {"keep.md", "archive/old.md"}


class TestRulesFiles:
    def test_default_rules_files_dropped_at_root(self, tmp_path):
        _write(tmp_path, "keep.md", "")
        _write(tmp_path, "CLAUDE.md", "Agent rules, not vault content.\n")
        _write(tmp_path, "CLAUDE.local.md", "Local agent rules.\n")
        graph = _build(tmp_path)
        assert set(graph.nodes) == {"keep.md"}

    def test_rules_files_dropped_at_any_depth(self, tmp_path):
        _write(tmp_path, "keep.md", "")
        _write(tmp_path, "sub/CLAUDE.md", "Nested agent rules.\n")
        graph = _build(tmp_path)
        assert set(graph.nodes) == {"keep.md"}

    def test_rules_file_contributes_no_edges(self, tmp_path):
        _write(tmp_path, "keep.md", "")
        _write(tmp_path, "CLAUDE.md", "Rules mentioning [[keep]].\n")
        graph = _build(tmp_path)
        assert graph.back_links["keep.md"] == set()

    def test_custom_rules_files_replace_the_defaults(self, tmp_path):
        _write(tmp_path, "keep.md", "")
        _write(tmp_path, "RULES.md", "Custom rules file.\n")
        _write(tmp_path, "CLAUDE.md", "No longer a rules file for this vault.\n")
        graph = _build(tmp_path, rules_files=["RULES.md"])
        assert set(graph.nodes) == {"keep.md", "CLAUDE.md"}

    def test_empty_rules_files_keeps_everything(self, tmp_path):
        _write(tmp_path, "keep.md", "")
        _write(tmp_path, "CLAUDE.md", "")
        graph = _build(tmp_path, rules_files=[])
        assert set(graph.nodes) == {"keep.md", "CLAUDE.md"}


class TestFiltersCompose:
    def test_scoped_excluded_and_rules_filters_all_apply_together(self, tmp_path):
        _write(tmp_path, "brain/keep.md", "")
        _write(tmp_path, "brain/archive/old.md", "")
        _write(tmp_path, "brain/CLAUDE.md", "")
        _write(tmp_path, "outside/note.md", "")
        graph = _build(
            tmp_path,
            scoped_folders=["brain"],
            excluded_dirs=["archive"],
            rules_files=["CLAUDE.md"],
        )
        assert set(graph.nodes) == {"brain/keep.md"}


@pytest.mark.parametrize(
    "excluded,expected",
    [
        ([], {"keep.md", "archive/old.md"}),
        (["archive"], {"keep.md"}),
        (["nonexistent"], {"keep.md", "archive/old.md"}),
    ],
)
def test_excluded_dirs_parametrized(tmp_path, excluded, expected):
    _write(tmp_path, "keep.md", "")
    _write(tmp_path, "archive/old.md", "")
    graph = _build(tmp_path, excluded_dirs=excluded)
    assert set(graph.nodes) == expected
