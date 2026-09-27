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

An entry may also set an optional ``link_syntax`` key (``"wikilink"`` | ``"markdown"`` |
``"both"`` | ``"markdown-autolinks"``, see ``graphmark.config.LINK_SYNTAXES``); it defaults to
``"wikilink"`` when absent, matching every entry in the manifest today.
"""

from __future__ import annotations

import re
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
    link_syntax: str = "wikilink"


def load_manifest(path: Path) -> list[CorpusVault]:
    """Load the corpus manifest TOML at ``path`` into a list of ``CorpusVault``.

    Raises ``ValueError`` if a ``[[vault]]`` entry is missing a required field (or a required
    string field is empty), or if two entries share the same ``name``.
    """
    path = Path(path)
    with open(path, "rb") as f:
        data = tomllib.load(f)

    # link_syntax is optional (defaults to "wikilink" below) and must stay excluded here: every
    # dataclass field is otherwise required, and none of the real manifest entries set it.
    required = [f.name for f in fields(CorpusVault) if f.name != "link_syntax"]
    vaults: list[CorpusVault] = []
    seen_names_casefold: dict[str, str] = {}

    for entry in data.get("vault", []):
        missing = [key for key in required if key not in entry]
        if missing:
            raise ValueError(f"manifest {path}: vault entry missing required field(s) {missing}")

        for key in _REQUIRED_STR_FIELDS:
            if not entry[key]:
                raise ValueError(f"manifest {path}: vault entry has empty required field '{key}'")

        name = entry["name"]
        if "/" in name or "\\" in name or ".." in name or name == ".":
            raise ValueError(
                f"manifest {path}: vault entry has invalid vault name {name!r} "
                "(must not contain '/', '\\', or '..', and must not be '.')"
            )

        if not re.fullmatch(r"[0-9a-f]{40}", entry["sha"]):
            raise ValueError(
                f"manifest {path}: vault entry has malformed sha '{entry['sha']}' "
                "(expected 40 lowercase hex characters)"
            )

        if entry["clone_url"].startswith("-"):
            raise ValueError(
                f"manifest {path}: vault entry has clone_url starting with '-': "
                f"'{entry['clone_url']}'"
            )

        excluded_dirs = entry["excluded_dirs"]
        if not isinstance(excluded_dirs, list) or not all(
            isinstance(item, str) for item in excluded_dirs
        ):
            raise ValueError(
                f"manifest {path}: vault entry has excluded_dirs that is not a list of "
                f"strings: {excluded_dirs!r}"
            )

        name_casefold = name.casefold()
        if name_casefold in seen_names_casefold:
            other = seen_names_casefold[name_casefold]
            raise ValueError(
                f"manifest {path}: duplicate vault name '{name}' (collides with '{other}')"
            )
        seen_names_casefold[name_casefold] = name

        vaults.append(
            CorpusVault(
                name=name,
                clone_url=entry["clone_url"],
                sha=entry["sha"],
                license=entry["license"],
                excluded_dirs=tuple(entry["excluded_dirs"]),
                link_syntax=entry.get("link_syntax", "wikilink"),
            )
        )

    return vaults
