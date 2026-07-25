"""Tests for model.py public surface.

Pins the model module to only the types the engine actually consumes, so the dead seeded
dataclasses (Edge/Graph/Finding) cut in the 0.2 honest-surface pass cannot silently reappear.
"""

from __future__ import annotations

import graphmark.model as model


def test_public_surface_is_document_only():
    assert model.__all__ == ["Document"]


def test_dead_dataclasses_are_removed():
    for removed in ("Edge", "Graph", "Finding"):
        assert not hasattr(model, removed), f"{removed} should be removed from model.py"


def test_document_still_present():
    assert hasattr(model, "Document")
