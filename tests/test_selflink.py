"""Self-links must form no edge — parity with brain_map (afk #9)."""

from __future__ import annotations

import json
from pathlib import Path

from graphmark.config import load_config
from graphmark.graph import NormalizeResolver, VaultGraph
from graphmark.metrics import bridges, clusters, hubs, orphans, stats
from graphmark.parse import WikilinkExtractor

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "selflink"
EXPECTED = json.loads((FIXTURE_DIR / "expected.json").read_text())


def _graph():
    cfg = load_config(FIXTURE_DIR / "config.toml")
    return VaultGraph.build(cfg, WikilinkExtractor(), NormalizeResolver())


def test_no_self_edges_anywhere():
    g = _graph()
    for node, targets in g.out_links.items():
        assert node not in targets, f"self-edge on {node}"
    for node, sources in g.back_links.items():
        assert node not in sources, f"self back-edge on {node}"


def test_structural_matches_oracle():
    g = _graph()
    cfg = load_config(FIXTURE_DIR / "config.toml")
    assert stats(g) == EXPECTED["stats"]
    assert orphans(g, cfg) == EXPECTED["orphans"]
    assert hubs(g) == EXPECTED["hubs"]
    assert clusters(g) == EXPECTED["clusters"]
    assert bridges(g) == EXPECTED["bridges"]
