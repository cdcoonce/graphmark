"""Tests for metrics.gaps — asserts against the FROZEN gaps/ oracle (afk #8 / issue #13)."""

from __future__ import annotations

import json
from pathlib import Path

from graphmark.config import load_config
from graphmark.graph import NormalizeResolver, VaultGraph
from graphmark.interfaces import Similarity
from graphmark.metrics import gaps
from graphmark.parse import WikilinkExtractor

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "gaps"
EXPECTED = json.loads((FIXTURE_DIR / "expected.json").read_text())
_MAP = {
    k: v
    for k, v in json.loads((FIXTURE_DIR / "similar.json").read_text()).items()
    if not k.startswith("_")
}


def _similar_fn(rel, k):
    return [tuple(x) for x in _MAP.get(rel, [])][:k]


def _graph():
    cfg = load_config(FIXTURE_DIR / "config.toml")
    return VaultGraph.build(cfg, WikilinkExtractor(), NormalizeResolver())


def test_gaps_matches_frozen_oracle():
    p = EXPECTED["params"]
    result = gaps(
        _graph(),
        _similar_fn,
        threshold=p["threshold"],
        k=p["k"],
        max_score=p["max_score"],
        hub_degree=p["hub_degree"],
        dismissed=set(p["dismissed"]),
    )
    assert result == EXPECTED["gaps"]


def test_plain_function_satisfies_similarity_protocol():
    # A plain function with the (rel_path, k) -> list[(rel_path, score)] shape is a valid
    # Similarity; assigning to the annotated type documents the seam and gaps() accepts it.
    fn: Similarity = _similar_fn
    result = gaps(_graph(), fn)
    assert isinstance(result, list)


def test_tied_reciprocal_pair_orientation_is_scan_order_independent():
    """A tied-score reciprocal pair must not depend on which direction is scanned first.

    Both notes report the SAME score for the other (a genuine tie), so the winner-selection
    `>` never fires for the later direction — without canonicalization, whichever note is
    scanned first (driven by `targets` order) wins the `a` slot arbitrarily.
    """
    empty: dict[str, set[str]] = {"a/one.md": set(), "b/two.md": set()}
    graph = VaultGraph(
        nodes={"a/one.md": None, "b/two.md": None},
        out_links=dict(empty),
        back_links=dict(empty),
    )

    def _tied_similar(rel, k):
        mapping = {
            "a/one.md": [("b/two.md", 0.8)],
            "b/two.md": [("a/one.md", 0.8)],
        }
        return mapping.get(rel, [])[:k]

    forward = gaps(graph, _tied_similar, targets=["a/one.md", "b/two.md"])
    backward = gaps(graph, _tied_similar, targets=["b/two.md", "a/one.md"])

    assert len(forward) == 1
    assert len(backward) == 1
    forward_ab = {"a": forward[0]["a"], "b": forward[0]["b"]}
    backward_ab = {"a": backward[0]["a"], "b": backward[0]["b"]}
    assert forward_ab == backward_ab
