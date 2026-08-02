"""Tests for scripts/corpus/diff.py: diff_reports and load_expected.

Uses hand-authored dicts matching scripts/corpus/report.py's build_vault_report output shape
(vault/notes/links/buckets), so this needs no network access and no real corpus vault checkout.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.corpus.diff import diff_reports, load_expected  # noqa: E402

_EMPTY_BUCKETS = {
    "resolved": {"count": 0, "share": 0.0},
    "ambiguous": {"count": 0, "share": 0.0},
    "non-note-file": {"count": 0, "share": 0.0},
    "out-of-scope-note": {"count": 0, "share": 0.0},
    "missing": {"count": 0, "share": 0.0},
    "intra-note": {"count": 0, "share": 0.0},
}


def _report(**overrides):
    report = {
        "vault": "synthetic-vault",
        "notes": 2,
        "links": 2,
        "buckets": {reason: dict(counts) for reason, counts in _EMPTY_BUCKETS.items()},
    }
    report.update(overrides)
    return report


def test_identical_reports_have_no_drift():
    expected = _report()
    actual = _report()

    assert diff_reports(expected, actual) == []


def test_changed_bucket_count_and_share_produce_diff_lines():
    expected = _report()
    actual = _report()
    actual["buckets"]["resolved"] = {"count": 1, "share": 0.5}
    actual["buckets"]["missing"] = {"count": 1, "share": 0.5}

    lines = diff_reports(expected, actual)

    assert "synthetic-vault · buckets.resolved.count · 0 → 1" in lines
    assert "synthetic-vault · buckets.resolved.share · 0.0 → 0.5" in lines
    assert "synthetic-vault · buckets.missing.count · 0 → 1" in lines
    assert "synthetic-vault · buckets.missing.share · 0.0 → 0.5" in lines
    assert len(lines) == 4


def test_changed_notes_and_links_produce_diff_lines():
    expected = _report()
    actual = _report(notes=3, links=5)

    lines = diff_reports(expected, actual)

    assert lines == [
        "synthetic-vault · notes · 2 → 3",
        "synthetic-vault · links · 2 → 5",
    ]


def test_mismatched_vault_raises():
    expected = _report(vault="vault-a")
    actual = _report(vault="vault-b")

    with pytest.raises(ValueError, match="vault"):
        diff_reports(expected, actual)


def test_load_expected_missing_file_raises(tmp_path):
    with pytest.raises(ValueError, match="not found"):
        load_expected(tmp_path / "missing.json")


def test_load_expected_invalid_json_raises(tmp_path):
    bad_path = tmp_path / "bad.json"
    bad_path.write_text("{not valid json")

    with pytest.raises(ValueError, match="invalid JSON"):
        load_expected(bad_path)


def test_load_expected_reads_valid_report(tmp_path):
    good_path = tmp_path / "good.json"
    good_path.write_text('{"vault": "v", "notes": 1, "links": 0, "buckets": {}}')

    assert load_expected(good_path) == {
        "vault": "v",
        "notes": 1,
        "links": 0,
        "buckets": {},
    }
