"""Tests for export.py: to_json and to_dot.

DOT assertions check structure against the trusted graph — no golden .dot file is authored.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from graphmark.config import VaultConfig
from graphmark.export import to_dot, to_json
from graphmark.graph import NormalizeResolver, VaultGraph
from graphmark.metrics import stats
from graphmark.parse import WikilinkExtractor

SIMPLE_VAULT = Path(__file__).parent / "fixtures" / "simple" / "vault"


@pytest.fixture(scope="module")
def simple_graph() -> VaultGraph:
    return VaultGraph.build(
        VaultConfig(root=SIMPLE_VAULT),
        WikilinkExtractor(),
        NormalizeResolver(),
    )


class TestToJson:
    def test_returns_string(self):
        assert isinstance(to_json({"key": "value"}), str)

    def test_parses_as_json(self):
        result = to_json({"a": 1, "b": [2, 3]})
        parsed = json.loads(result)
        assert parsed == {"a": 1, "b": [2, 3]}

    def test_roundtrips_stats(self, simple_graph):
        obj = stats(simple_graph)
        assert json.loads(to_json(obj)) == obj

    def test_roundtrips_list(self):
        obj = [["a/b.md", 0.5], ["c/d.md", 0.3]]
        assert json.loads(to_json(obj)) == obj


class TestToDot:
    def test_is_digraph(self, simple_graph):
        result = to_dot(simple_graph)
        assert result.strip().startswith("digraph")

    def test_has_opening_and_closing_brace(self, simple_graph):
        result = to_dot(simple_graph)
        assert "{" in result
        assert result.strip().endswith("}")

    def test_contains_all_nodes(self, simple_graph):
        result = to_dot(simple_graph)
        for node in simple_graph.nodes:
            assert node in result, f"node {node!r} missing from DOT output"

    def test_contains_all_directed_edges(self, simple_graph):
        result = to_dot(simple_graph)
        for src, targets in simple_graph.out_links.items():
            for dst in targets:
                edge_str = f'"{src}" -> "{dst}"'
                assert edge_str in result, f"edge {edge_str!r} missing from DOT output"

    def test_isolated_nodes_present(self, simple_graph):
        result = to_dot(simple_graph)
        assert "reference/island.md" in result
        assert "reference/stub.md" in result

    def test_edge_count_matches_graph(self, simple_graph):
        result = to_dot(simple_graph)
        edge_count = result.count(" -> ")
        expected = sum(len(targets) for targets in simple_graph.out_links.values())
        assert edge_count == expected
