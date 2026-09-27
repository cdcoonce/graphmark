"""Vault-health gating: evaluate a CheckPolicy against a built graph.

This is policy evaluation, not a structural metric — it composes existing metrics with the
thresholds from the config's ``[check]`` block into a report shaped for CI consumption. The
report is byte-stable: key insertion order is fixed here, and checks appear in ``CheckPolicy``
field-declaration order, so two runs over an unchanged vault diff to nothing.
"""

from __future__ import annotations

from dataclasses import fields

from graphmark.config import VaultConfig
from graphmark.graph import DIAGNOSIS_REASONS, VaultGraph
from graphmark.metrics import orphans, siloed_notes


def unresolved_link_count(graph: VaultGraph, *, config: VaultConfig | None = None) -> int:
    """Total unresolved link OCCURRENCES across the vault (not distinct targets).

    With no ``config`` (the default), every occurrence counts — byte-identical to this
    function's behavior before issue #256. With ``config`` given, occurrences whose source
    note (the key in ``graph.unresolved``) starts with any ``config.transient_prefixes`` entry
    are excluded, the same ``str.startswith`` test ``orphans`` uses (metrics.py).
    """
    if config is None:
        return sum(len(displays) for displays in graph.unresolved.values())
    return sum(
        len(displays)
        for note, displays in graph.unresolved.items()
        if not any(note.startswith(prefix) for prefix in config.transient_prefixes)
    )


def links_report(graph: VaultGraph) -> dict:
    """How every wikilink in the vault was classified, as a byte-stable block.

    The counts exist on the graph after a build, but a vault owner cannot read a Python object.
    That gap is not cosmetic: the six-release frontmatter-alias defect was legible in this
    distribution the entire time — many links reported broken beside zero resolved via alias — and
    nobody saw it because no surface printed it.

    Key order is fixed here and reasons follow ``DIAGNOSIS_REASONS``, so two runs over an unchanged
    vault diff to nothing, matching ``run_check``'s existing contract.
    """
    counts = {reason: graph.link_counts.get(reason, 0) for reason in DIAGNOSIS_REASONS}
    return {
        "total": sum(counts.values()),
        "counts": counts,
        "alias_resolved": graph.alias_resolved,
    }


def links_summary_line(report: dict) -> str:
    """One human-readable line of the distribution, for stderr."""
    parts = [f"{reason} {count}" for reason, count in report["counts"].items()]
    parts.append(f"alias-resolved {report['alias_resolved']}")
    return " · ".join(parts)


# Maps a CheckPolicy field name to the callable that computes its "actual" value. Honors
# transient_prefixes for max_orphans (scratch/daily notes do not fail the gate) and passes
# config= through to unresolved_link_count for the same reason (issue #256). An unwired field
# name raises the dict's natural KeyError; TestDispatchMappingWired (tests/test_check.py) is what
# makes an unwired CheckPolicy field visible at test time rather than at first real invocation.
_DISPATCH = {
    "max_orphans": lambda g, c: len(orphans(g, c)),
    "max_unresolved_links": lambda g, c: unresolved_link_count(g, config=c),
    "max_siloed": lambda g, c: len(siloed_notes(g)),
}


def _actual(name: str, graph: VaultGraph, config: VaultConfig) -> int:
    return _DISPATCH[name](graph, config)


def run_check(graph: VaultGraph, config: VaultConfig) -> dict:
    """Evaluate ``config.check`` against ``graph`` and return the report.

    Raises ``ValueError`` when the policy enforces nothing: a gate with no thresholds would
    otherwise report a meaningless green, which is worse than failing loudly.
    """
    policy = config.check
    if not policy.is_configured():
        names = ", ".join(f.name for f in fields(config.check))
        raise ValueError(
            "no [check] policy configured: set at least one threshold in the config's "
            f"[check] table ({names})"
        )

    checks = []
    for f in fields(policy):
        limit = getattr(policy, f.name)
        if limit is None:
            continue
        actual = _actual(f.name, graph, config)
        # "max" is inclusive: exactly at the limit passes.
        checks.append({"name": f.name, "limit": limit, "actual": actual, "pass": actual <= limit})

    # `links` is appended, never interleaved, so consumers already parsing this report keep
    # working. It is context for reading the verdict and can never change it.
    return {
        "pass": all(c["pass"] for c in checks),
        "checks": checks,
        "links": links_report(graph),
    }


def breach_lines(report: dict) -> list[str]:
    """One human-readable line per breached check, for stderr."""
    return [
        f"{c['name']}: {c['actual']} exceeds limit {c['limit']}"
        for c in report["checks"]
        if not c["pass"]
    ]
