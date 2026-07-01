"""Vault configuration — the domain seam that makes the engine general.

``VaultConfig`` holds every vault-specific policy the engine consults. ``load_config`` (TOML →
VaultConfig) is intentionally left unimplemented; wiring config through the engine is afk Issue #3.
Fixture tests may construct ``VaultConfig`` directly.
"""

from __future__ import annotations

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


def load_config(path: Path) -> VaultConfig:  # noqa: ARG001
    """Load a VaultConfig from a TOML file. Implemented in afk Issue #3."""
    raise NotImplementedError("load_config is afk Issue #3 (config layer + generalization)")
