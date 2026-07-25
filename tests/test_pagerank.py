"""Tests for metrics.pagerank — asserts against FROZEN oracles (simple + alt).

Matching BOTH fixtures proves the implementation generalises (not overfit to simple's 6 values).
All expected values are from tests/fixtures/*/expected.json — do NOT edit those files.
"""

from __future__ import annotations

import json
from pathlib import Path

import networkx as nx
import pytest

from graphmark.config import VaultConfig, load_config
from graphmark.graph import NormalizeResolver, VaultGraph
from graphmark.metrics import pagerank
from graphmark.parse import WikilinkExtractor

SIMPLE_DIR = Path(__file__).parent / "fixtures" / "simple"
ALT_DIR = Path(__file__).parent / "fixtures" / "alt"

SIMPLE_EXPECTED = json.loads((SIMPLE_DIR / "expected.json").read_text())
ALT_EXPECTED = json.loads((ALT_DIR / "expected.json").read_text())

TOLERANCE = 1e-4


@pytest.fixture(scope="module")
def simple_graph() -> VaultGraph:
    return VaultGraph.build(
        VaultConfig(root=SIMPLE_DIR / "vault"),
        WikilinkExtractor(),
        NormalizeResolver(),
    )


@pytest.fixture(scope="module")
def alt_graph() -> VaultGraph:
    cfg = load_config(ALT_DIR / "config.toml")
    return VaultGraph.build(cfg, WikilinkExtractor(), NormalizeResolver())


class TestPagerankSimple:
    def test_ranking_length_matches_oracle(self, simple_graph):
        result = pagerank(simple_graph)
        assert len(result) == len(SIMPLE_EXPECTED["pagerank"]["ranking"])

    def test_ranking_paths_match_oracle_order(self, simple_graph):
        result = pagerank(simple_graph)
        oracle = SIMPLE_EXPECTED["pagerank"]["ranking"]
        for i, (path, _) in enumerate(result):
            assert path == oracle[i][0], f"position {i}: got {path!r}, expected {oracle[i][0]!r}"

    def test_ranking_scores_within_tolerance(self, simple_graph):
        result = pagerank(simple_graph)
        oracle = SIMPLE_EXPECTED["pagerank"]["ranking"]
        for i, (path, score) in enumerate(result):
            expected_score = oracle[i][1]
            assert abs(score - expected_score) < TOLERANCE, (
                f"{path}: got {score:.6f}, expected {expected_score:.6f}"
            )

    def test_sorted_score_desc(self, simple_graph):
        result = pagerank(simple_graph)
        scores = [s for _, s in result]
        for i in range(len(scores) - 1):
            assert scores[i] >= scores[i + 1]

    def test_n_limits_results(self, simple_graph):
        result = pagerank(simple_graph, n=3)
        assert len(result) == 3
        oracle = SIMPLE_EXPECTED["pagerank"]["ranking"]
        assert result[0][0] == oracle[0][0]
        assert result[1][0] == oracle[1][0]
        assert result[2][0] == oracle[2][0]

    def test_returns_list_of_pairs(self, simple_graph):
        result = pagerank(simple_graph)
        for item in result:
            assert len(item) == 2
            assert isinstance(item[0], str)
            assert isinstance(item[1], float)


class TestPagerankAlt:
    def test_ranking_length_matches_oracle(self, alt_graph):
        result = pagerank(alt_graph, n=10)
        assert len(result) == len(ALT_EXPECTED["pagerank"]["ranking"])

    def test_ranking_paths_match_oracle_order(self, alt_graph):
        result = pagerank(alt_graph, n=10)
        oracle = ALT_EXPECTED["pagerank"]["ranking"]
        for i, (path, _) in enumerate(result):
            assert path == oracle[i][0], f"position {i}: got {path!r}, expected {oracle[i][0]!r}"

    def test_ranking_scores_within_tolerance(self, alt_graph):
        result = pagerank(alt_graph, n=10)
        oracle = ALT_EXPECTED["pagerank"]["ranking"]
        for i, (path, score) in enumerate(result):
            expected_score = oracle[i][1]
            assert abs(score - expected_score) < TOLERANCE, (
                f"{path}: got {score:.6f}, expected {expected_score:.6f}"
            )

    def test_all_nodes_included_when_n_sufficient(self, alt_graph):
        result = pagerank(alt_graph, n=10)
        result_paths = {p for p, _ in result}
        assert result_paths == set(alt_graph.nodes.keys())


class TestPagerankAlphaValidation:
    """alpha outside (0, 1) is not a damping factor — it must not silently produce numbers."""

    @pytest.mark.parametrize("bad_alpha", [0.0, 1.0, 1.5, -0.5, 2.0])
    def test_out_of_range_alpha_raises(self, simple_graph, bad_alpha):
        with pytest.raises(ValueError, match="alpha"):
            pagerank(simple_graph, alpha=bad_alpha)

    @pytest.mark.parametrize("good_alpha", [0.5, 0.85, 0.95])
    def test_in_range_alpha_still_works(self, simple_graph, good_alpha):
        result = pagerank(simple_graph, alpha=good_alpha)
        assert len(result) == len(simple_graph.nodes)
        assert all(score > 0 for _, score in result)


class TestPagerankConvergence:
    """networkx raises PowerIterationFailedConvergence at max_iter; so must we."""

    @staticmethod
    def _chain(n: int) -> VaultGraph:
        nodes = {f"n{i}.md": None for i in range(n)}
        out = {f"n{i}.md": ({f"n{i + 1}.md"} if i < n - 1 else set()) for i in range(n)}
        back = {f"n{i}.md": ({f"n{i - 1}.md"} if i > 0 else set()) for i in range(n)}
        return VaultGraph(nodes=nodes, out_links=out, back_links=back)

    def test_non_converging_graph_raises_instead_of_returning(self):
        # A 200-node chain at alpha=0.999 does not reach tolerance within 100 iterations.
        graph = self._chain(200)
        with pytest.raises(nx.PowerIterationFailedConvergence):
            pagerank(graph, alpha=0.999)

    def test_converging_graph_returns_normally(self):
        graph = self._chain(200)
        result = pagerank(graph, alpha=0.85, n=5)
        assert len(result) == 5
