"""Degenerate-vault behavior and the networkx cross-check the ROADMAP claims but never enforced.

Two untested regions:
  * the empty-vault guard branches (`density ... if notes > 0`, `if N == 0: return []`) — a
    PyPI user's likely first contact is pointing the CLI at the wrong or an empty directory;
  * "PageRank is checked against networkx" (docs/ROADMAP.md) had no enforcing test, even though
    networkx is already the sole runtime dependency.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import networkx as nx
import pytest
from networkx.algorithms.link_analysis.pagerank_alg import _pagerank_python

from graphmark.config import VaultConfig, load_config
from graphmark.export import to_dot
from graphmark.graph import NormalizeResolver, VaultGraph
from graphmark.metrics import (
    bridges,
    clusters,
    gaps,
    hubs,
    neighborhood,
    orphans,
    pagerank,
    siloed_notes,
    stats,
)
from graphmark.parse import WikilinkExtractor

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _build(root: Path) -> VaultGraph:
    return VaultGraph.build(VaultConfig(root=root), WikilinkExtractor(), NormalizeResolver())


@pytest.fixture
def empty_vault(tmp_path) -> Path:
    vault = tmp_path / "empty-vault"
    vault.mkdir()
    return vault


class TestEmptyVault:
    """An existing but empty vault is legitimate and must produce empty, valid results."""

    def test_builds_with_no_nodes(self, empty_vault):
        graph = _build(empty_vault)
        assert graph.nodes == {}
        assert graph.out_links == {}
        assert graph.back_links == {}

    def test_stats_are_all_zero(self, empty_vault):
        assert stats(_build(empty_vault)) == {
            "notes": 0,
            "edges": 0,
            "orphans": 0,
            "clusters": 0,
            "density": 0.0,
        }

    def test_density_guard_returns_float_zero_not_a_division_error(self, empty_vault):
        density = stats(_build(empty_vault))["density"]
        assert isinstance(density, float)
        assert density == 0.0

    def test_list_metrics_are_empty(self, empty_vault):
        graph = _build(empty_vault)
        config = VaultConfig(root=empty_vault)
        assert orphans(graph, config) == []
        assert hubs(graph) == []
        assert clusters(graph) == []
        assert bridges(graph) == []
        assert siloed_notes(graph) == []

    def test_pagerank_returns_empty_list(self, empty_vault):
        assert pagerank(_build(empty_vault)) == []

    def test_gaps_returns_empty_list(self, empty_vault):
        graph = _build(empty_vault)
        assert gaps(graph, lambda _rel, _k: [("never.md", 0.9)]) == []

    def test_to_dot_emits_a_valid_empty_digraph(self, empty_vault):
        assert to_dot(_build(empty_vault)) == "digraph G {\n}"

    def test_neighborhood_on_any_note_raises(self, empty_vault):
        with pytest.raises(ValueError, match="unknown note"):
            neighborhood(_build(empty_vault), "anything.md")

    def test_cli_stats_exits_0_with_valid_json(self, empty_vault, capsys):
        from graphmark.cli import main

        with patch.object(sys, "argv", ["graphmark", "--root", str(empty_vault), "stats"]):
            main()
        out = capsys.readouterr().out
        assert json.loads(out)["notes"] == 0


class TestSingleNoteVault:
    """One note, no links — the smallest non-empty vault."""

    @pytest.fixture
    def one_note(self, tmp_path) -> Path:
        vault = tmp_path / "one"
        vault.mkdir()
        (vault / "solo.md").write_text("# Solo\n\nNo links here.\n", encoding="utf-8")
        return vault

    def test_stats(self, one_note):
        assert stats(_build(one_note)) == {
            "notes": 1,
            "edges": 0,
            "orphans": 1,
            "clusters": 0,
            "density": 0.0,
        }

    def test_the_note_is_an_orphan_and_not_a_hub(self, one_note):
        graph = _build(one_note)
        assert orphans(graph, VaultConfig(root=one_note)) == ["solo.md"]
        assert hubs(graph) == []

    def test_pagerank_gives_the_only_note_all_the_mass(self, one_note):
        result = pagerank(_build(one_note))
        assert len(result) == 1
        assert result[0][0] == "solo.md"
        assert result[0][1] == pytest.approx(1.0, abs=1e-6)


class TestPagerankMatchesNetworkx:
    """Makes the ROADMAP's 'checked against networkx' claim real.

    graphmark's docstring claims parity with networkx's pure-python implementation
    (_pagerank_python); nx.pagerank itself dispatches to a scipy backend, and this package
    deliberately ships no numpy/scipy. Tolerance 1e-5 sits far below any teleport/convergence
    mutation (which shifts scores by ~1e-2) while staying above graphmark's own N*1e-6
    convergence tolerance.
    """

    TOLERANCE = 1e-5

    @staticmethod
    def _as_digraph(graph: VaultGraph) -> nx.DiGraph:
        D: nx.DiGraph = nx.DiGraph()
        D.add_nodes_from(graph.nodes)
        for src, targets in graph.out_links.items():
            for dst in targets:
                D.add_edge(src, dst)
        return D

    @pytest.mark.parametrize("fixture", ["simple", "alt"])
    @pytest.mark.parametrize("alpha", [0.5, 0.85, 0.95])
    def test_matches_networkx_pure_python(self, fixture, alpha):
        cfg = load_config(FIXTURE_DIR / fixture / "config.toml")
        graph = VaultGraph.build(cfg, WikilinkExtractor(), NormalizeResolver())
        mine = dict(pagerank(graph, n=len(graph.nodes), alpha=alpha))
        theirs = _pagerank_python(self._as_digraph(graph), alpha=alpha, tol=1e-10, max_iter=1000)
        assert set(mine) == set(theirs)
        for node, score in mine.items():
            assert abs(score - theirs[node]) < self.TOLERANCE, (
                f"{fixture} alpha={alpha} {node}: {score:.9f} vs nx {theirs[node]:.9f}"
            )

    @pytest.mark.parametrize("fixture", ["simple", "alt"])
    def test_scores_sum_to_one(self, fixture):
        cfg = load_config(FIXTURE_DIR / fixture / "config.toml")
        graph = VaultGraph.build(cfg, WikilinkExtractor(), NormalizeResolver())
        total = sum(score for _, score in pagerank(graph, n=len(graph.nodes)))
        assert total == pytest.approx(1.0, abs=1e-6)
