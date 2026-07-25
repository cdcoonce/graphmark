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


class TestCorruptStore:
    def test_invalid_json_load_returns_empty(self, tmp_path):
        store = tmp_path / dismiss._DEFAULT_PATH
        store.parent.mkdir(parents=True, exist_ok=True)
        store.write_text("{ not valid json")
        assert dismiss.load_dismissed(tmp_path) == {}
        assert dismiss.active_dismissed_sigs(tmp_path) == set()

    def test_non_dict_json_does_not_crash(self, tmp_path):
        store = tmp_path / dismiss._DEFAULT_PATH
        store.parent.mkdir(parents=True, exist_ok=True)
        store.write_text('["a", "b"]')  # valid JSON, wrong shape
        assert dismiss.load_dismissed(tmp_path) == {}
        assert dismiss.active_dismissed_sigs(tmp_path) == set()


class TestSigRoundTrip:
    """gaps() emits sigs, callers persist them via record_dismissal, and feed
    active_dismissed_sigs back in as dismissed=. One definition must serve all three."""

    def test_gaps_sig_matches_weaklink_sig(self):
        from graphmark.dismiss import weaklink_sig
        from graphmark.graph import VaultGraph
        from graphmark.metrics import gaps

        graph = VaultGraph(
            nodes={"a/one.md": None, "b/two.md": None},
            out_links={"a/one.md": set(), "b/two.md": set()},
            back_links={"a/one.md": set(), "b/two.md": set()},
        )
        result = gaps(graph, lambda _rel, _k: [("b/two.md", 0.8)])
        assert len(result) == 1
        assert result[0]["sig"] == weaklink_sig("a/one.md", "b/two.md")

    def test_dismissing_a_gaps_suggestion_suppresses_it_on_the_next_run(self, tmp_path):
        """The full loop: suggest -> record -> re-run -> suppressed."""
        from graphmark import dismiss
        from graphmark.graph import VaultGraph
        from graphmark.metrics import gaps

        (tmp_path / "one.md").write_text("first")
        (tmp_path / "two.md").write_text("second")
        graph = VaultGraph(
            nodes={"one.md": None, "two.md": None},
            out_links={"one.md": set(), "two.md": set()},
            back_links={"one.md": set(), "two.md": set()},
        )

        def similar(rel, k):
            return [("two.md", 0.8)] if rel == "one.md" else []

        first = gaps(graph, similar)
        assert len(first) == 1
        sig = first[0]["sig"]

        dismiss.record_dismissal(tmp_path, "one.md", "two.md")
        active = dismiss.active_dismissed_sigs(tmp_path)
        # The sig gaps() emitted is exactly the one the store now holds.
        assert sig in active
        assert gaps(graph, similar, dismissed=active) == []
