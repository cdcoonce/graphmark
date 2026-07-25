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
    transient_prefixes: tuple[str, ...] = ()


def load_config(path: Path, *, root_override: Path | None = None) -> VaultConfig:
    """Load a VaultConfig from a TOML file.

    ``root`` is the only required key (resolved relative to the TOML's directory). Every other
    key that maps to a ``VaultConfig`` field is optional and falls back to the dataclass default;
    any other key in the TOML is silently ignored. A TOML missing ``root`` raises ``ValueError``
    naming the file and the missing key.

    ``root_override`` supplies the vault root from outside the TOML (the CLI's ``--root`` flag).
    When given it wins over any ``root`` key and makes that key optional, so a policy-only config
    — such as the shipped ``configs/my-brain.toml`` — can be paired with an explicit root.
    """
    with open(path, "rb") as f:
        data = tomllib.load(f)

    if root_override is not None:
        root = root_override
    elif "root" in data:
        root = path.parent / data["root"]
    else:
        raise ValueError(f"config {path}: missing required key 'root'")

    return VaultConfig(
        root=root,
        scoped_folders=data.get("scoped_folders", []),
        excluded_dirs=data.get("excluded_dirs", []),
        rules_files=data.get("rules_files", ["CLAUDE.md", "CLAUDE.local.md"]),
        transient_prefixes=tuple(data.get("transient_prefixes", [])),
    )
