"""Core data model for graphmark.

These dataclasses are the seeded boundaries the engine is built against. Do not rename
their types or fields; implement the engine modules to produce and consume them.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Document:
    """A single note in the vault."""

    rel_path: str  # posix rel-path from vault root, e.g. "brain/North Star.md"
    text: str
    frontmatter: dict


@dataclass(frozen=True)
class Edge:
    """A resolved directed link from one note to another."""

    src: str  # rel_path
    dst: str  # rel_path


@dataclass
class Graph:
    """The built graph: nodes plus resolved out/back adjacency."""

    nodes: dict[str, Document]  # rel_path -> Document
    out_links: dict[str, set[str]]  # rel_path -> resolved target rel_paths
    back_links: dict[str, set[str]]  # inverted out_links


@dataclass(frozen=True)
class Finding:
    """A health finding (used by health checks)."""

    kind: str  # "orphan" | "broken_link" | "missing_frontmatter"
    note: str  # rel_path
    detail: str = ""
