"""Core data model for graphmark.

``Document`` is the only model type the engine consumes; the resolved graph is
``graph.VaultGraph``. Do not rename ``Document``'s type or fields.
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
