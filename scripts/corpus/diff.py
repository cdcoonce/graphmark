"""Drift detection — compare a freshly built corpus report against a frozen expected one.

``diff_reports`` and ``load_expected`` are the two halves of the harness's diff mode: given an
expected report (loaded from a file checked into ``docs/corpus/expected/``) and an actual report
(freshly built by ``scripts/corpus/report.py``), describe every changed number.
"""

from __future__ import annotations

import json
from pathlib import Path

from graphmark.graph import DIAGNOSIS_REASONS

_TOP_LEVEL_FIELDS = ("notes", "links")
_BUCKET_FIELDS = ("count", "share")


def diff_reports(expected: dict, actual: dict) -> list[str]:
    """Return one formatted drift line per changed field between ``expected`` and ``actual``.

    Raises ``ValueError`` if the two reports are for different vaults -- comparing two different
    vaults' reports is a usage error, not drift.
    """
    if expected["vault"] != actual["vault"]:
        raise ValueError(
            f"cannot diff reports for different vaults: "
            f"{expected['vault']!r} != {actual['vault']!r}"
        )

    vault = actual["vault"]
    lines = []

    for field in _TOP_LEVEL_FIELDS:
        before, after = expected[field], actual[field]
        if before != after:
            lines.append(f"{vault} · {field} · {before} → {after}")

    for reason in DIAGNOSIS_REASONS:
        for field in _BUCKET_FIELDS:
            before = expected["buckets"][reason][field]
            after = actual["buckets"][reason][field]
            if before != after:
                lines.append(f"{vault} · buckets.{reason}.{field} · {before} → {after}")

    return lines


def load_expected(path: Path) -> dict:
    """Load a frozen expected report from ``path``, raising ``ValueError`` if that fails."""
    try:
        return json.loads(path.read_text())
    except FileNotFoundError as exc:
        raise ValueError(f"expected report not found: {path}") from exc
    except OSError as exc:
        raise ValueError(f"could not read expected report {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"expected report {path} contains invalid JSON: {exc}") from exc
