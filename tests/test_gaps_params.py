"""Parameter-level tests for metrics.gaps — the knobs the frozen oracle never exercises.

The gaps/ fixture pins the ranking algorithm end-to-end, but it always calls gaps() with the
same shape: no note=, no targets=, no exclude_prefixes, no self-pairs, and fixture scores that
never sit exactly on the threshold or max_score bound. Every one of those was a mutation the
suite could not kill. These use an in-memory graph plus a stub similarity source so each knob
is isolated.
"""

from __future__ import annotations

import pytest

from graphmark.graph import VaultGraph
from graphmark.metrics import gaps


def _graph(*rel_paths: str, edges: dict[str, set[str]] | None = None) -> VaultGraph:
    """Build an in-memory graph; edges maps src -> set of dst (back_links inverted)."""
    nodes = dict.fromkeys(rel_paths)
    out: dict[str, set[str]] = {rel: set() for rel in rel_paths}
    back: dict[str, set[str]] = {rel: set() for rel in rel_paths}
    for src, dsts in (edges or {}).items():
        out[src] = set(dsts)
        for dst in dsts:
            back[dst].add(src)
    return VaultGraph(nodes=nodes, out_links=out, back_links=back)


class _RecordingSimilarity:
    """A Similarity stub that records which rel_paths it was asked about."""

    def __init__(self, mapping: dict[str, list[tuple[str, float]]]):
        self.mapping = mapping
        self.calls: list[str] = []

    def __call__(self, rel_path: str, k: int) -> list[tuple[str, float]]:
        self.calls.append(rel_path)
        return self.mapping.get(rel_path, [])[:k]


def _pairs(result) -> set[frozenset[str]]:
    return {frozenset((r["a"], r["b"])) for r in result}


class TestScoreBoundaries:
    """threshold and max_score are INCLUSIVE bounds — a score exactly on either is kept."""

    def _run(self, score: float, **kwargs):
        graph = _graph("a/one.md", "b/two.md")
        fn = _RecordingSimilarity({"a/one.md": [("b/two.md", score)]})
        return gaps(graph, fn, **kwargs)

    def test_score_equal_to_threshold_is_kept(self):
        assert len(self._run(0.6, threshold=0.6)) == 1

    def test_score_just_below_threshold_is_dropped(self):
        assert self._run(0.5999, threshold=0.6) == []

    def test_score_equal_to_max_score_is_kept(self):
        assert len(self._run(0.92, threshold=0.0, max_score=0.92)) == 1

    def test_score_just_above_max_score_is_dropped(self):
        assert self._run(0.9201, threshold=0.0, max_score=0.92) == []


class TestTargetScoping:
    """note= and targets= restrict WHICH notes are scanned, not just what is returned."""

    def _fixture(self):
        graph = _graph("a/one.md", "b/two.md", "c/three.md")
        fn = _RecordingSimilarity(
            {
                "a/one.md": [("b/two.md", 0.8)],
                "b/two.md": [("c/three.md", 0.8)],
                "c/three.md": [("a/one.md", 0.8)],
            }
        )
        return graph, fn

    def test_default_scans_every_note(self):
        graph, fn = self._fixture()
        gaps(graph, fn)
        assert sorted(fn.calls) == ["a/one.md", "b/two.md", "c/three.md"]

    def test_note_restricts_the_scan_to_that_note(self):
        graph, fn = self._fixture()
        result = gaps(graph, fn, note="a/one.md")
        assert fn.calls == ["a/one.md"]
        assert _pairs(result) == {frozenset({"a/one.md", "b/two.md"})}

    def test_targets_restricts_the_scan_to_the_list(self):
        graph, fn = self._fixture()
        gaps(graph, fn, targets=["a/one.md", "c/three.md"])
        assert sorted(fn.calls) == ["a/one.md", "c/three.md"]

    def test_note_takes_precedence_over_targets(self):
        # Documented precedence: note= wins. (Whether the conflict should raise instead is
        # an API decision tracked separately.)
        graph, fn = self._fixture()
        gaps(graph, fn, note="a/one.md", targets=["b/two.md", "c/three.md"])
        assert fn.calls == ["a/one.md"]

    def test_empty_targets_scans_nothing(self):
        graph, fn = self._fixture()
        assert gaps(graph, fn, targets=[]) == []
        assert fn.calls == []


class TestExcludePrefixes:
    def test_excludes_on_the_source_side(self):
        graph = _graph("daily/log.md", "b/two.md")
        fn = _RecordingSimilarity({"daily/log.md": [("b/two.md", 0.8)]})
        assert gaps(graph, fn, exclude_prefixes=("daily/",)) == []
        # The excluded note is skipped before the similarity source is consulted for it.
        assert "daily/log.md" not in fn.calls

    def test_excludes_on_the_candidate_side(self):
        graph = _graph("a/one.md", "daily/log.md")
        fn = _RecordingSimilarity({"a/one.md": [("daily/log.md", 0.8)]})
        assert gaps(graph, fn, exclude_prefixes=("daily/",)) == []
        assert fn.calls == ["a/one.md"]  # scanned, but the candidate was filtered

    def test_unrelated_prefix_does_not_exclude(self):
        graph = _graph("a/one.md", "b/two.md")
        fn = _RecordingSimilarity({"a/one.md": [("b/two.md", 0.8)]})
        assert len(gaps(graph, fn, exclude_prefixes=("daily/",))) == 1

    def test_multiple_prefixes_all_apply(self):
        graph = _graph("a/one.md", "daily/log.md", "tmp/scratch.md")
        fn = _RecordingSimilarity({"a/one.md": [("daily/log.md", 0.8), ("tmp/scratch.md", 0.8)]})
        assert gaps(graph, fn, exclude_prefixes=("daily/", "tmp/")) == []


class TestSelfPairAndLinked:
    def test_self_pair_from_similarity_source_yields_no_suggestion(self):
        graph = _graph("a/one.md", "b/two.md")
        fn = _RecordingSimilarity({"a/one.md": [("a/one.md", 0.99), ("b/two.md", 0.8)]})
        result = gaps(graph, fn)
        assert _pairs(result) == {frozenset({"a/one.md", "b/two.md"})}

    def test_already_linked_pair_is_dropped_in_either_direction(self):
        graph = _graph("a/one.md", "b/two.md", edges={"a/one.md": {"b/two.md"}})
        # b -> a is only a BACK-link, but the pair is still linked and must be suppressed.
        fn = _RecordingSimilarity({"b/two.md": [("a/one.md", 0.9)]})
        assert gaps(graph, fn) == []


class TestKPassthrough:
    @pytest.mark.parametrize("k,expected", [(1, 1), (2, 2), (5, 2)])
    def test_k_limits_candidates_via_the_similarity_source(self, k, expected):
        graph = _graph("a/one.md", "b/two.md", "c/three.md")
        fn = _RecordingSimilarity({"a/one.md": [("b/two.md", 0.9), ("c/three.md", 0.8)]})
        assert len(gaps(graph, fn, note="a/one.md", k=k)) == expected


class TestCrossFolder:
    """Folder-locality in _rank_key: two root-level notes (no "/" in rel_path) must compare as
    same-folder, and any note with a folder component must keep comparing by its existing
    top-level path segment (issue #216)."""

    def test_root_level_notes_are_not_cross_folder(self):
        # "one.md" and "two.md" are both root-level (no "/"), so they must rank as same-folder
        # despite "two.md" scoring higher. "sub/three.md" is genuinely cross-folder and, despite
        # its lower score, must rank first. Equal scores would fall through to the a/b tie-break
        # and pass even under the pre-fix bug, so the scores are deliberately unequal.
        graph = _graph("one.md", "two.md", "sub/three.md")
        fn = _RecordingSimilarity({"one.md": [("two.md", 0.9), ("sub/three.md", 0.5)]})
        result = gaps(graph, fn, note="one.md")
        assert [frozenset({r["a"], r["b"]}) for r in result] == [
            frozenset({"one.md", "sub/three.md"}),
            frozenset({"one.md", "two.md"}),
        ]

    def test_two_level_nesting_still_ranks_by_top_level_segment(self):
        # Both "docs/sub1/x.md" and "docs/sub2/y.md" share the top-level segment "docs", so they
        # must keep ranking as same-folder today -- a dirname-based comparison would instead see
        # "docs/sub1" != "docs/sub2" and treat them as cross-folder, reversing this order.
        graph = _graph("docs/sub1/x.md", "docs/sub2/y.md", "other/z.md")
        fn = _RecordingSimilarity(
            {"docs/sub1/x.md": [("docs/sub2/y.md", 0.9), ("other/z.md", 0.5)]}
        )
        result = gaps(graph, fn, note="docs/sub1/x.md")
        assert [frozenset({r["a"], r["b"]}) for r in result] == [
            frozenset({"docs/sub1/x.md", "other/z.md"}),
            frozenset({"docs/sub1/x.md", "docs/sub2/y.md"}),
        ]
