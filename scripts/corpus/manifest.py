"""Corpus manifest — pins the third-party vaults used by the corpus study harness.

``CorpusVault`` records one pinned vault; ``load_manifest`` reads a TOML file shaped like::

    [[vault]]
    name = "arkalim-obsidian-vault"
    clone_url = "https://github.com/arkalim/obsidian-vault"
    sha = "<pinned commit sha>"
    license = "MIT"
    excluded_dirs = [".git", ".obsidian", ".github"]

into a list of ``CorpusVault``. This is a sibling harness module, not part of the graphmark
engine, but follows ``graphmark/config.py``'s style (frozen dataclass, ``tomllib``, ``Path``-based
loader) for consistency.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, fields
from pathlib import Path

_REQUIRED_STR_FIELDS = ("name", "clone_url", "sha", "license")


@dataclass(frozen=True)
class CorpusVault:
    """One pinned third-party vault in the corpus."""

    name: str
    clone_url: str
    sha: str
    license: str
    excluded_dirs: tuple[str, ...]


def load_manifest(path: Path) -> list[CorpusVault]:
    """Load the corpus manifest TOML at ``path`` into a list of ``CorpusVault``.

    Raises ``ValueError`` if a ``[[vault]]`` entry is missing a required field (or a required
    string field is empty), or if two entries share the same ``name``.
    """
    path = Path(path)
    with open(path, "rb") as f:
        data = tomllib.load(f)

    required = [f.name for f in fields(CorpusVault)]
    vaults: list[CorpusVault] = []
    seen_names: set[str] = set()

    for entry in data.get("vault", []):
        missing = [key for key in required if key not in entry]
        if missing:
            raise ValueError(f"manifest {path}: vault entry missing required field(s) {missing}")

        for key in _REQUIRED_STR_FIELDS:
            if not entry[key]:
                raise ValueError(f"manifest {path}: vault entry has empty required field '{key}'")

        name = entry["name"]
        if name in seen_names:
            raise ValueError(f"manifest {path}: duplicate vault name '{name}'")
        seen_names.add(name)

        vaults.append(
            CorpusVault(
                name=name,
                clone_url=entry["clone_url"],
                sha=entry["sha"],
                license=entry["license"],
                excluded_dirs=tuple(entry["excluded_dirs"]),
            )
        )

    return vaults
