"""Core data model for graphmark.

``Document`` is the seeded boundary the engine is built against. Do not rename its type or
fields; implement the engine modules to produce and consume it.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["Document"]


@dataclass(frozen=True)
class Document:
    """A single note in the vault."""

    rel_path: str  # posix rel-path from vault root, e.g. "brain/North Star.md"
    text: str
    frontmatter: dict
