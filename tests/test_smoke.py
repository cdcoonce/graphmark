"""Baseline smoke test so the gate is green before the engine exists.

afk replaces/augments this with real tests (asserting against tests/fixtures/*/expected.json) as it
builds each module.
"""

import graphmark
from graphmark import model


def test_package_imports():
    assert graphmark.__version__ == "0.1.0"


def test_model_public_surface_is_document_only():
    assert model.__all__ == ["Document"]
    for name in ("Edge", "Graph", "Finding"):
        assert not hasattr(model, name), f"model.{name} should have been removed"
