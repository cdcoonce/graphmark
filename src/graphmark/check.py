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


def unresolved_links(graph: VaultGraph, *, config: VaultConfig | None = None) -> list[list[str]]:
    """Every unresolved link OCCURRENCE as ``[source note, target]``, sorted by source.

    Same filter as ``unresolved_link_count``, which is its length: with ``config`` given, sources
    starting with any ``config.transient_prefixes`` entry are dropped. A link repeated in one note
    appears once per occurrence, because that is what the count counts.
    """
    prefixes = () if config is None else tuple(config.transient_prefixes)
    return [
        [note, target]
        for note in sorted(graph.unresolved)
        if not any(note.startswith(prefix) for prefix in prefixes)
        for target in graph.unresolved[note]
    ]


def unresolved_link_count(graph: VaultGraph, *, config: VaultConfig | None = None) -> int:
    """Total unresolved link OCCURRENCES across the vault (not distinct targets).

    With no ``config`` (the default), every occurrence counts — byte-identical to this
    function's behavior before issue #256. With ``config`` given, occurrences whose source
    note (the key in ``graph.unresolved``) starts with any ``config.transient_prefixes`` entry
    are excluded, the same ``str.startswith`` test ``orphans`` uses (metrics.py).
    """
    return len(unresolved_links(graph, config=config))


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


# Maps a CheckPolicy field name to the callable that lists its offenders; a check's "actual" is
# that list's length, so the count and the names a reader is shown cannot disagree. Honors
# transient_prefixes for max_orphans (scratch/daily notes do not fail the gate) and passes
# config= through to unresolved_link_count for the same reason (issue #256). An unwired field
# name raises the dict's natural KeyError; TestDispatchMappingWired (tests/test_check.py) is what
# makes an unwired CheckPolicy field visible at test time rather than at first real invocation.
_DISPATCH = {
    "max_orphans": lambda g, c: orphans(g, c),
    "max_unresolved_links": lambda g, c: unresolved_links(g, config=c),
    "max_siloed": lambda g, c: siloed_notes(g),
}


def _offenders(name: str, graph: VaultGraph, config: VaultConfig) -> list:
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
        offenders = _offenders(f.name, graph, config)
        actual = len(offenders)
        # "max" is inclusive: exactly at the limit passes. `offenders` is appended last so
        # consumers already parsing name/limit/actual/pass keep working.
        checks.append(
            {
                "name": f.name,
                "limit": limit,
                "actual": actual,
                "pass": actual <= limit,
                "offenders": offenders,
            }
        )

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


def _offender_line(offender: str | list[str]) -> str:
    if isinstance(offender, list):
        source, target = offender
        return f"  {source} → [[{target}]]"
    return f"  {offender}"


def breach_detail_lines(report: dict) -> list[str]:
    """``breach_lines``, each followed by its check's offenders, indented, for stderr.

    Unresolved links read ``source → [[target]]``; orphaned and siloed notes are their paths.
    """
    lines = []
    for c in report["checks"]:
        if c["pass"]:
            continue
        lines.append(f"{c['name']}: {c['actual']} exceeds limit {c['limit']}")
        lines.extend(_offender_line(o) for o in c["offenders"])
    return lines
