"""Baseline smoke test so the gate is green before the engine exists.

afk replaces/augments this with real tests (asserting against tests/fixtures/*/expected.json) as it
builds each module.
"""

import importlib.metadata

import graphmark


def test_package_imports():
    assert graphmark.__version__ == importlib.metadata.version("graphmark")
