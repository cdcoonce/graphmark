"""Pluggable interfaces — the generality seams.

Only the default wikilink/normalize implementations are required now; these Protocols exist so
alternate link syntaxes and resolution strategies can be added later without touching the engine.
"""

from __future__ import annotations

from typing import Protocol


class LinkExtractor(Protocol):
    """Extracts raw link displays from note text."""

    def extract(self, text: str) -> list[str]:
        """Return raw link displays found in ``text``, excluding links inside code spans.

        A "display" is the inner text of a link before resolution, e.g. ``[[Note|alias]]`` yields
        ``"Note|alias"`` (alias/anchor stripping happens in the Resolver).
        """
        ...


class Resolver(Protocol):
    """Resolves a link display to a target note."""

    def resolve(self, display: str, catalog: dict[str, list[str]]) -> str | None:
        """Resolve ``display`` to a target rel_path, or ``None`` if unresolved/ambiguous.

        ``catalog`` maps a normalized note key to the list of rel_paths sharing that key (length > 1
        means a collision → a bare link to it is ambiguous and must not resolve).
        """
        ...
