"""gaps() must not crash when similar_fn returns a note outside the graph (afk #10)."""

from __future__ import annotations

import json
from pathlib import Path

from graphmark.config import load_config
from graphmark.graph import NormalizeResolver, VaultGraph
from graphmark.metrics import gaps
from graphmark.parse import WikilinkExtractor

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "gaps"
EXPECTED = json.loads((FIXTURE_DIR / "expected_oog.json").read_text())
_MAP = {
    k: v
    for k, v in json.loads((FIXTURE_DIR / "similar_oog.json").read_text()).items()
    if not k.startswith("_")
}


def _similar_fn(rel, k):
    return [tuple(x) for x in _MAP.get(rel, [])][:k]


def _graph():
    cfg = load_config(FIXTURE_DIR / "config.toml")
    return VaultGraph.build(cfg, WikilinkExtractor(), NormalizeResolver())


def test_gaps_tolerates_out_of_graph_nodes():
    p = EXPECTED["params"]
    result = gaps(
        _graph(),
        _similar_fn,
        threshold=p["threshold"],
        k=p["k"],
        max_score=p["max_score"],
        hub_degree=p["hub_degree"],
    )
    assert result == EXPECTED["gaps"]
