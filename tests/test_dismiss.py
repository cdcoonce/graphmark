"""Tests for dismiss.py — asserts against the FROZEN dismiss/ oracle (afk #7 / issue #12).

The active-sig set was computed by brain_map.py's own active_dismissed_sigs(); this test pins
graphmark to that reference output. Oracle authored + frozen by the human conductor; do not edit
tests/fixtures/dismiss/ to make a test pass.
"""

from __future__ import annotations

import json
from pathlib import Path

from graphmark import dismiss

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "dismiss"
VAULT = FIXTURE_DIR / "vault"
EXPECTED = json.loads((FIXTURE_DIR / "expected.json").read_text())


class TestActiveDismissedSigs:
    def test_matches_frozen_oracle(self):
        got = sorted(dismiss.active_dismissed_sigs(VAULT))
        assert got == EXPECTED["active_sigs"]

    def test_only_alpha_beta_active(self):
        # alpha|gamma is stale (gamma content changed); alpha|delta is stale (delta missing).
        active = dismiss.active_dismissed_sigs(VAULT)
        assert "weaklink|alpha.md|beta.md" in active
        assert "weaklink|alpha.md|gamma.md" not in active
        assert "weaklink|alpha.md|delta.md" not in active

    def test_all_recorded_sigs_present_in_store(self):
        assert sorted(dismiss.load_dismissed(VAULT).keys()) == EXPECTED["all_sigs"]


class TestWeaklinkSig:
    def test_order_independent_and_sorted(self):
        assert dismiss.weaklink_sig("b.md", "a.md") == "weaklink|a.md|b.md"
        assert dismiss.weaklink_sig("a.md", "b.md") == dismiss.weaklink_sig("b.md", "a.md")


class TestRecordDismissalRoundTrip:
    def test_record_then_active(self, tmp_path):
        (tmp_path / "x.md").write_text("x content")
        (tmp_path / "y.md").write_text("y content")
        dismiss.record_dismissal(tmp_path, "x.md", "y.md")
        sig = dismiss.weaklink_sig("x.md", "y.md")
        assert sig in dismiss.load_dismissed(tmp_path)
        assert sig in dismiss.active_dismissed_sigs(tmp_path)

    def test_stale_after_content_change(self, tmp_path):
        (tmp_path / "x.md").write_text("x content")
        (tmp_path / "y.md").write_text("y content")
        dismiss.record_dismissal(tmp_path, "x.md", "y.md")
        (tmp_path / "y.md").write_text("y CHANGED")  # invalidates the recorded hash
        assert dismiss.active_dismissed_sigs(tmp_path) == set()
