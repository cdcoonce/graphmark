"""Vault configuration — the domain seam that makes the engine general.

``VaultConfig`` holds every vault-specific policy the engine consults. ``load_config`` reads a
TOML file into a ``VaultConfig`` (paths resolved relative to the TOML's directory). Fixture tests
may construct ``VaultConfig`` directly.
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
    wikilink_pattern: str = r"\[\[(.+?)\]\]"
    orphan_min_chars: int = 300
    transient_prefixes: tuple[str, ...] = ()


def load_config(path: Path) -> VaultConfig:
    """Load a VaultConfig from a TOML file.

    ``root`` is required. All other keys are optional and fall back to the
    ``VaultConfig`` dataclass defaults when absent.
    """
    with open(path, "rb") as f:
        data = tomllib.load(f)

    if "root" not in data:
        raise ValueError(f"config {path}: missing required key 'root'")

    toml_dir = path.parent
    root = toml_dir / data["root"]

    return VaultConfig(
        root=root,
        scoped_folders=data.get("scoped_folders", []),
        excluded_dirs=data.get("excluded_dirs", []),
        rules_files=data.get("rules_files", ["CLAUDE.md", "CLAUDE.local.md"]),
        wikilink_pattern=data.get("wikilink_pattern", r"\[\[(.+?)\]\]"),
        orphan_min_chars=data.get("orphan_min_chars", 300),
        transient_prefixes=tuple(data.get("transient_prefixes", [])),
    )
