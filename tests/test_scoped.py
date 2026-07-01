"""Tests for scoped_folders include-list — asserts against FROZEN oracle (scoped fixture).

scoped_folders=['docs','refs'] must exclude misc/ and junk/ entirely: those notes are absent
from the graph and links originating there must not appear as back-edges.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from graphmark.config import load_config
from graphmark.graph import NormalizeResolver, VaultGraph
from graphmark.metrics import bridges, clusters, hubs, orphans, stats
from graphmark.parse import WikilinkExtractor

SCOPED_DIR = Path(__file__).parent / "fixtures" / "scoped"
EXPECTED = json.loads((SCOPED_DIR / "expected.json").read_text())


@pytest.fixture(scope="module")
def scoped_graph() -> VaultGraph:
    cfg = load_config(SCOPED_DIR / "config.toml")
    return VaultGraph.build(cfg, WikilinkExtractor(), NormalizeResolver())


@pytest.fixture(scope="module")
def scoped_cfg():
    return load_config(SCOPED_DIR / "config.toml")


class TestScopedFolders:
    def test_only_in_scope_nodes_present(self, scoped_graph):
        assert set(scoped_graph.nodes.keys()) == {"docs/one.md", "refs/two.md"}

    def test_out_of_scope_notes_absent(self, scoped_graph):
        assert "misc/excluded.md" not in scoped_graph.nodes
        assert "junk/ignored.md" not in scoped_graph.nodes

    def test_out_of_scope_back_link_not_present(self, scoped_graph):
        # misc/excluded.md links to [[one]] — must NOT appear as a back-edge on docs/one.md
        assert "misc/excluded.md" not in scoped_graph.back_links.get("docs/one.md", set())

    def test_stats_match_oracle(self, scoped_graph):
        result = stats(scoped_graph)
        assert result == EXPECTED["stats"]

    def test_orphans_match_oracle(self, scoped_graph, scoped_cfg):
        result = orphans(scoped_graph, scoped_cfg)
        assert result == EXPECTED["orphans"]

    def test_hubs_match_oracle(self, scoped_graph):
        result = hubs(scoped_graph)
        assert result == EXPECTED["hubs"]

    def test_clusters_match_oracle(self, scoped_graph):
        result = clusters(scoped_graph)
        assert result == EXPECTED["clusters"]

    def test_bridges_match_oracle(self, scoped_graph):
        result = bridges(scoped_graph)
        assert result == EXPECTED["bridges"]
