"""Vault configuration — the domain seam that makes the engine general.

``VaultConfig`` holds every vault-specific policy the engine consults. ``load_config`` reads a
TOML file into a ``VaultConfig`` (paths resolved relative to the TOML's directory). Fixture tests
may construct ``VaultConfig`` directly.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field, fields
from pathlib import Path

#: Every value ``VaultConfig.link_syntax`` accepts. A consumer may switch on these, so the set is
#: part of the config contract.
LINK_SYNTAXES = frozenset({"wikilink", "markdown", "both"})


@dataclass(frozen=True)
class CheckPolicy:
    """Vault-health thresholds for ``graphmark check``; ``None`` means "not enforced".

    Field declaration order is the report order, so it is part of the check contract.
    """

    max_orphans: int | None = None
    max_unresolved_links: int | None = None
    max_siloed: int | None = None

    def is_configured(self) -> bool:
        """True when at least one threshold is enforced.

        A gate with nothing to check must not be able to report green, so callers use this to
        refuse rather than trivially pass.
        """
        return any(
            getattr(self, f.name) is not None
            for f in fields(self)  # noqa: B009 - dataclass
        )


@dataclass
class VaultConfig:
    """All vault-specific behavior, parametrized."""

    root: Path
    scoped_folders: list[str] = field(default_factory=list)
    excluded_dirs: list[str] = field(default_factory=list)
    rules_files: list[str] = field(default_factory=lambda: ["CLAUDE.md", "CLAUDE.local.md"])
    transient_prefixes: tuple[str, ...] = ()
    # Obsidian's `aliases:` property names a note, so links written against one resolve by
    # default. Set False for strict basename-only resolution.
    resolve_aliases: bool = True
    #: Which link syntax to read. ``"wikilink"`` (the default) is Obsidian's ``[[Note]]`` and is
    #: what every frozen fixture encodes, so the default keeps existing behavior byte-identical.
    #: ``"markdown"`` reads ``[text](note.md)``, the syntax non-Obsidian markdown vaults use — added
    #: on demand after a corpus vault turned out to have 11,198 of them and zero extracted edges.
    #: ``"both"`` reads each, which is what Obsidian itself accepts.
    link_syntax: str = "wikilink"
    check: CheckPolicy = field(default_factory=CheckPolicy)

    def __post_init__(self) -> None:
        # A string root would otherwise survive construction and fail much later with an
        # obscure AttributeError on the first Path operation.
        if not isinstance(self.root, Path):
            self.root = Path(self.root)
        # Fail loudly rather than silently reading nothing: a typo here would produce an empty
        # graph, which is exactly the failure #151 exists to make visible.
        if self.link_syntax not in LINK_SYNTAXES:
            raise ValueError(
                f"link_syntax must be one of {sorted(LINK_SYNTAXES)}, got {self.link_syntax!r}"
            )


def _parse_check(data: dict, path: Path) -> CheckPolicy:
    """Parse the optional [check] table.

    Unknown keys inside [check] are an ERROR, unlike unknown keys elsewhere in the TOML: a
    silently-ignored typo would produce a gate that reports green forever, which is the worst
    failure mode a CI gate can have.
    """
    raw = data.get("check", {})
    if not isinstance(raw, dict):
        raise ValueError(f"config {path}: [check] must be a table, got {type(raw).__name__}")

    valid = [f.name for f in fields(CheckPolicy)]
    for key in raw:
        if key not in valid:
            raise ValueError(
                f"config {path}: unknown key '{key}' in [check]; valid keys are {valid}"
            )

    values: dict[str, int] = {}
    for key in valid:
        if key not in raw:
            continue
        value = raw[key]
        # bool is an int subclass in Python; a boolean threshold is a config error, not 0/1.
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError(
                f"config {path}: [check].{key} must be a non-negative integer, got {value!r}"
            )
        values[key] = value
    return CheckPolicy(**values)


def load_config(path: str | Path, *, root_override: str | Path | None = None) -> VaultConfig:
    """Load a VaultConfig from a TOML file.

    ``root`` is the only required key (resolved relative to the TOML's directory). Every other
    key that maps to a ``VaultConfig`` field is optional and falls back to the dataclass default;
    any other key in the TOML is silently ignored. A TOML missing ``root`` raises ``ValueError``
    naming the file and the missing key.

    The one exception to that leniency is the optional ``[check]`` table (see ``CheckPolicy``):
    an unknown key or a non-negative-integer value there raises, because a silently-ignored
    typo would leave a CI gate reporting green forever.

    ``root_override`` supplies the vault root from outside the TOML (the CLI's ``--root`` flag).
    When given it wins over any ``root`` key and makes that key optional, so a policy-only config
    — such as the shipped ``configs/my-brain.toml`` — can be paired with an explicit root.
    """
    path = Path(path)
    with open(path, "rb") as f:
        data = tomllib.load(f)

    if root_override is not None:
        root = Path(root_override)
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
        resolve_aliases=bool(data.get("resolve_aliases", True)),
        link_syntax=data.get("link_syntax", "wikilink"),
        check=_parse_check(data, path),
    )
