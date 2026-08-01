"""Per-vault corpus report — a byte-stable JSON summary built on graphmark's public surface.

``build_vault_report`` and ``report_json`` reuse ``graphmark.build`` and
``graphmark.check.links_report`` rather than recomputing bucket counts themselves, so this module
carries no parallel accounting path: if the reference engine's link classification changes, this
report changes with it automatically.
"""

from __future__ import annotations

import json
from pathlib import Path

import graphmark
from graphmark.check import links_report
from graphmark.graph import DIAGNOSIS_REASONS
from scripts.corpus.manifest import CorpusVault


def build_vault_report(vault: CorpusVault, cache_root: Path) -> dict:
    """Build the report dict for ``vault``, whose checkout lives at ``cache_root / vault.name``."""
    config = graphmark.VaultConfig(
        root=cache_root / vault.name, excluded_dirs=list(vault.excluded_dirs)
    )
    graph = graphmark.build(config)
    report = links_report(graph)
    total = report["total"]

    buckets = {}
    for reason in DIAGNOSIS_REASONS:
        count = report["counts"][reason]
        share = round(count / total, 4) if total else 0.0
        buckets[reason] = {"count": count, "share": share}

    return {
        "vault": vault.name,
        "notes": len(graph.nodes),
        "links": total,
        "buckets": buckets,
    }


def report_json(vault: CorpusVault, cache_root: Path) -> str:
    """Byte-stable JSON text for ``build_vault_report(vault, cache_root)``."""
    return json.dumps(build_vault_report(vault, cache_root), indent=2, sort_keys=True) + "\n"
