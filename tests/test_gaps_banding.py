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
