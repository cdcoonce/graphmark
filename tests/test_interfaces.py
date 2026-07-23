"""Tests for interfaces.py — the pluggable-seam Protocols."""

from __future__ import annotations

from graphmark.interfaces import Similarity


def test_plain_function_satisfies_similarity_seam() -> None:
    def plain_similar_fn(rel_path: str, k: int) -> list[tuple[str, float]]:
        return [("other.md", 0.9)][:k]

    sim: Similarity = plain_similar_fn
    assert sim("note.md", 5) == [("other.md", 0.9)]
