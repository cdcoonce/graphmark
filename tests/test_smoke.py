"""Baseline smoke test so the gate is green before the engine exists.

afk replaces/augments this with real tests (asserting against tests/fixtures/*/expected.json) as it
builds each module.
"""

from importlib.metadata import version

import graphmark


def test_package_imports():
    # Version is single-sourced from package metadata (pyproject) — no duplicated literal.
    assert graphmark.__version__ == version("graphmark")
