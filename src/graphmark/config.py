"""Vault configuration — the domain seam that makes the engine general.

``VaultConfig`` holds every vault-specific policy the engine consults. ``load_config`` reads a
TOML file into a ``VaultConfig`` (paths resolved relative to the TOML's directory). Fixture tests
may construct ``VaultConfig`` directly. TOML keys with no matching ``VaultConfig`` field (unknown
keys, or fields removed from the schema) are silently ignored, not validated against.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class VaultConfig:
    """All vault-specific behavior, parametrized."""

    root: Path
    scoped_folders: list[str] = field(default_factory=list)
    excluded_dirs: list[str] = field(default_factory=list)
    rules_files: list[str] = field(default_factory=lambda: ["CLAUDE.md", "CLAUDE.local.md"])
    transient_prefixes: tuple[str, ...] = ()


def load_config(path: Path) -> VaultConfig:
    """Load a VaultConfig from a TOML file."""
    with open(path, "rb") as f:
        data = tomllib.load(f)

    toml_dir = path.parent
    root = toml_dir / data["root"]

    return VaultConfig(
        root=root,
        scoped_folders=data.get("scoped_folders", []),
        excluded_dirs=data.get("excluded_dirs", []),
        rules_files=data.get("rules_files", ["CLAUDE.md", "CLAUDE.local.md"]),
        transient_prefixes=tuple(data.get("transient_prefixes", [])),
    )
