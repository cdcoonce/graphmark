"""Pins the published gaps banding defaults (afk #32).

These constants are the validated band proven in daily /connect + /garden use on the owner's
live vault; consumers opt in by passing them to gaps(). gaps()'s own signature defaults are left
unchanged (non-breaking), so the frozen gaps fixtures — which pass explicit parameters — are
unaffected.
"""

from __future__ import annotations

from graphmark import metrics


def test_published_band_values():
    assert metrics.GAPS_DEFAULT_THRESHOLD == 0.6
    assert metrics.GAPS_DEFAULT_MAX_SCORE == 0.92
    assert metrics.GAPS_DEFAULT_K == 8
    assert metrics.GAPS_DEFAULT_HUB_DEGREE == 40


def test_gaps_signature_defaults_unchanged():
    # Option 1 is non-breaking: gaps() keeps its original, unvalidated signature defaults.
    import inspect

    params = inspect.signature(metrics.gaps).parameters
    assert params["threshold"].default == 0.0
    assert params["k"].default == 5
    assert params["max_score"].default is None
    assert params["hub_degree"].default is None


def test_band_dict_matches_the_individual_constants():
    assert metrics.GAPS_DEFAULT_BAND == {
        "threshold": metrics.GAPS_DEFAULT_THRESHOLD,
        "max_score": metrics.GAPS_DEFAULT_MAX_SCORE,
        "k": metrics.GAPS_DEFAULT_K,
        "hub_degree": metrics.GAPS_DEFAULT_HUB_DEGREE,
    }


def test_band_dict_splats_into_gaps():
    """The whole point: opting into the validated band is one gesture, not four."""
    import inspect

    from graphmark.graph import VaultGraph

    params = inspect.signature(metrics.gaps).parameters
    assert set(metrics.GAPS_DEFAULT_BAND) <= set(params), "band keys must be real gaps() kwargs"

    graph = VaultGraph(
        nodes={"a/one.md": None, "b/two.md": None},
        out_links={"a/one.md": set(), "b/two.md": set()},
        back_links={"a/one.md": set(), "b/two.md": set()},
    )
    # 0.8 sits inside the validated band (0.6 <= 0.8 <= 0.92), so it survives.
    result = metrics.gaps(graph, lambda _rel, _k: [("b/two.md", 0.8)], **metrics.GAPS_DEFAULT_BAND)
    assert len(result) == 1


def test_splatting_the_band_does_not_mutate_it():
    """Splatting passes a copy, so a caller cannot corrupt the band for everyone else."""
    from graphmark.graph import VaultGraph

    snapshot = dict(metrics.GAPS_DEFAULT_BAND)
    empty = VaultGraph(nodes={}, out_links={}, back_links={})
    metrics.gaps(empty, lambda _rel, _k: [], **metrics.GAPS_DEFAULT_BAND)
    assert snapshot == metrics.GAPS_DEFAULT_BAND


def test_note_and_targets_together_is_supported():
    """The live consumer (graph_cli.py) computes targets unconditionally while note stays
    optional, so passing both must keep working — note wins as the more specific scope."""
    from graphmark.graph import VaultGraph

    graph = VaultGraph(
        nodes={"a/one.md": None, "b/two.md": None},
        out_links={"a/one.md": set(), "b/two.md": set()},
        back_links={"a/one.md": set(), "b/two.md": set()},
    )
    scanned: list[str] = []

    def similar(rel: str, k: int):
        scanned.append(rel)
        return [("b/two.md", 0.8)] if rel == "a/one.md" else []

    result = metrics.gaps(graph, similar, note="a/one.md", targets=["b/two.md"])
    assert scanned == ["a/one.md"]
    assert len(result) == 1
