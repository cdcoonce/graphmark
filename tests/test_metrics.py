"""Tests for metrics.py: stats/orphans/hubs/clusters/bridges/neighborhood.

All assertions are derived from tests/fixtures/simple/expected.json (frozen oracle).
"""

import json
from pathlib import Path

import pytest

from graphmark.config import VaultConfig
from graphmark.graph import NormalizeResolver, VaultGraph
from graphmark.metrics import bridges, clusters, hubs, neighborhood, orphans, stats
from graphmark.parse import WikilinkExtractor

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "simple"
FIXTURE_VAULT = FIXTURE_DIR / "vault"
EXPECTED = json.loads((FIXTURE_DIR / "expected.json").read_text())


@pytest.fixture(scope="module")
def graph() -> VaultGraph:
    return VaultGraph.build(
        VaultConfig(root=FIXTURE_VAULT),
        WikilinkExtractor(),
        NormalizeResolver(),
    )


@pytest.fixture(scope="module")
def config() -> VaultConfig:
    return VaultConfig(root=FIXTURE_VAULT)


class TestStats:
    def test_notes_count(self, graph):
        result = stats(graph)
        assert result["notes"] == EXPECTED["stats"]["notes"]

    def test_edges_count(self, graph):
        result = stats(graph)
        assert result["edges"] == EXPECTED["stats"]["edges"]

    def test_orphan_count(self, graph):
        result = stats(graph)
        assert result["orphans"] == EXPECTED["stats"]["orphans"]

    def test_cluster_count(self, graph):
        result = stats(graph)
        assert result["clusters"] == EXPECTED["stats"]["clusters"]

    def test_density(self, graph):
        result = stats(graph)
        assert result["density"] == EXPECTED["stats"]["density"]

    def test_full_stats_shape(self, graph):
        result = stats(graph)
        assert set(result.keys()) == {"notes", "edges", "orphans", "clusters", "density"}


class TestOrphans:
    def test_matches_oracle(self, graph, config):
        result = orphans(graph, config)
        assert result == EXPECTED["orphans"]

    def test_returns_sorted_list(self, graph, config):
        result = orphans(graph, config)
        assert result == sorted(result)

    def test_transient_prefix_excludes_node(self, graph):
        cfg = VaultConfig(root=FIXTURE_VAULT, transient_prefixes=("reference/",))
        result = orphans(graph, cfg)
        assert "reference/island.md" not in result
        assert "reference/stub.md" not in result

    def test_no_transient_prefix_returns_both_orphans(self, graph, config):
        result = orphans(graph, config)
        assert len(result) == 2


class TestHubs:
    def test_matches_oracle(self, graph):
        result = hubs(graph)
        assert result == EXPECTED["hubs"]

    def test_sorted_by_degree_desc_then_path(self, graph):
        result = hubs(graph)
        degrees = [d for _, d in result]
        # degrees are non-increasing
        assert degrees == sorted(degrees, reverse=True)

    def test_top_n_limit(self, graph):
        result = hubs(graph, n=2)
        assert len(result) == 2
        assert result[0] == EXPECTED["hubs"][0]
        assert result[1] == EXPECTED["hubs"][1]

    def test_excludes_orphans_implicitly(self, graph):
        result = hubs(graph)
        paths = [p for p, _ in result]
        assert "reference/island.md" not in paths
        assert "reference/stub.md" not in paths

    def test_default_n_is_ten(self, graph):
        result = hubs(graph)
        # fixture has 4 non-orphan nodes; all should appear with default n=10
        assert len(result) == 4


class TestClusters:
    def test_matches_oracle(self, graph):
        result = clusters(graph)
        assert result == EXPECTED["clusters"]

    def test_singletons_omitted(self, graph):
        result = clusters(graph)
        for component in result:
            assert len(component) > 1

    def test_members_sorted(self, graph):
        result = clusters(graph)
        for component in result:
            assert component == sorted(component)

    def test_components_sorted_by_size_desc(self, graph):
        result = clusters(graph)
        sizes = [len(c) for c in result]
        assert sizes == sorted(sizes, reverse=True)


class TestBridges:
    def test_matches_oracle(self, graph):
        result = bridges(graph)
        assert result == EXPECTED["bridges"]

    def test_returns_sorted_list(self, graph):
        result = bridges(graph)
        assert result == sorted(result)


class TestNeighborhood:
    def test_hub_depth1(self, graph):
        args = EXPECTED["neighborhood"][0]["args"]
        expected = EXPECTED["neighborhood"][0]["expected"]
        result = neighborhood(graph, args["note"], depth=args["depth"])
        assert result == expected

    def test_hub_depth2_includes_two_hop(self, graph):
        args = EXPECTED["neighborhood"][1]["args"]
        expected = EXPECTED["neighborhood"][1]["expected"]
        result = neighborhood(graph, args["note"], depth=args["depth"])
        assert result == expected

    def test_beta_depth1(self, graph):
        args = EXPECTED["neighborhood"][2]["args"]
        expected = EXPECTED["neighborhood"][2]["expected"]
        result = neighborhood(graph, args["note"], depth=args["depth"])
        assert result == expected

    def test_depth1_has_no_two_hop_key(self, graph):
        result = neighborhood(graph, "brain/hub.md", depth=1)
        assert "two_hop" not in result

    def test_depth2_has_two_hop_key(self, graph):
        result = neighborhood(graph, "brain/hub.md", depth=2)
        assert "two_hop" in result

    def test_out_and_back_are_sorted(self, graph):
        result = neighborhood(graph, "personal/beta.md", depth=1)
        assert result["out"] == sorted(result["out"])
        assert result["back"] == sorted(result["back"])
