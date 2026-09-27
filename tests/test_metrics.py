"""Tests for metrics.py: stats/orphans/hubs/clusters/bridges/neighborhood/siloed_notes.

All assertions are derived from tests/fixtures/simple/expected.json (frozen oracle).
"""

import json
from pathlib import Path

import pytest

from graphmark.config import VaultConfig, load_config
from graphmark.graph import NormalizeResolver, VaultGraph
from graphmark.metrics import bridges, clusters, hubs, neighborhood, orphans, siloed_notes, stats
from graphmark.parse import WikilinkExtractor

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "simple"
FIXTURE_VAULT = FIXTURE_DIR / "vault"
EXPECTED = json.loads((FIXTURE_DIR / "expected.json").read_text())

ALT_DIR = Path(__file__).parent / "fixtures" / "alt"
ALT_EXPECTED = json.loads((ALT_DIR / "expected.json").read_text())


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


@pytest.fixture(scope="module")
def alt_graph() -> VaultGraph:
    cfg = load_config(ALT_DIR / "config.toml")
    return VaultGraph.build(cfg, WikilinkExtractor(), NormalizeResolver())


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

    def test_negative_n_raises_value_error(self, graph):
        with pytest.raises(ValueError, match="n"):
            hubs(graph, n=-1)


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

    def test_equal_size_components_tie_break_is_deterministic(self):
        # Two 2-node components {a.md, b.md} and {y.md, z.md} tie for largest. Build the same
        # graph twice with the components inserted in reversed order, so any dependence on
        # nx.connected_components' incidental traversal order (itself inherited from
        # node-insertion order) would flip which component comes first. The tie-break must make
        # both graphs agree on the same, lexicographically-ordered result regardless.
        nodes_forward = {"a.md": None, "b.md": None, "y.md": None, "z.md": None}
        out_links_forward = {"a.md": {"b.md"}, "b.md": set(), "y.md": {"z.md"}, "z.md": set()}
        back_links_forward = {"b.md": {"a.md"}, "a.md": set(), "z.md": {"y.md"}, "y.md": set()}
        g_forward = VaultGraph(
            nodes=nodes_forward, out_links=out_links_forward, back_links=back_links_forward
        )

        nodes_reversed = {"y.md": None, "z.md": None, "a.md": None, "b.md": None}
        out_links_reversed = {"y.md": {"z.md"}, "z.md": set(), "a.md": {"b.md"}, "b.md": set()}
        back_links_reversed = {"z.md": {"y.md"}, "y.md": set(), "b.md": {"a.md"}, "a.md": set()}
        g_reversed = VaultGraph(
            nodes=nodes_reversed, out_links=out_links_reversed, back_links=back_links_reversed
        )

        expected = [["a.md", "b.md"], ["y.md", "z.md"]]
        assert clusters(g_forward) == expected
        assert clusters(g_reversed) == expected


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

    def test_unknown_note_raises_valueerror_with_note(self, graph):
        with pytest.raises(ValueError, match="does/not/exist.md"):
            neighborhood(graph, "does/not/exist.md")


class TestSiloedNotes:
    def test_simple_no_bridges_returns_empty(self, graph):
        result = siloed_notes(graph)
        assert result == []

    def test_alt_matches_oracle(self, alt_graph):
        result = siloed_notes(alt_graph)
        assert result == ALT_EXPECTED["siloed"]

    def test_returns_sorted_list(self, alt_graph):
        result = siloed_notes(alt_graph)
        assert result == sorted(result)

    def test_no_duplicates(self, alt_graph):
        result = siloed_notes(alt_graph)
        assert len(result) == len(set(result))

    def test_equal_size_components_tie_break_is_deterministic(self):
        # center is the sole articulation point; removing it yields two size-1 components
        # {a.md} and {b.md} that tie for largest. The tie-break makes the lexicographically
        # smallest-membered component (a.md) the mainland, so b.md is the island — and the
        # result is identical across repeated runs, not dependent on traversal order.
        nodes = {"a.md": None, "b.md": None, "center.md": None}
        out_links = {"center.md": {"a.md", "b.md"}, "a.md": set(), "b.md": set()}
        back_links = {"a.md": {"center.md"}, "b.md": {"center.md"}, "center.md": set()}
        g = VaultGraph(nodes=nodes, out_links=out_links, back_links=back_links)
        first = siloed_notes(g)
        assert first == ["b.md"]
        assert siloed_notes(g) == first  # deterministic across runs
