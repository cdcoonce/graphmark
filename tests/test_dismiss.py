"""Tests for dismiss.py — asserts against the FROZEN dismiss/ oracle (afk #7 / issue #12).

The active-sig set was computed by brain_map.py's own active_dismissed_sigs(); this test pins
graphmark to that reference output. Oracle authored + frozen by the human conductor; do not edit
tests/fixtures/dismiss/ to make a test pass.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

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


class TestWeaklinkSigOrdinaryPathsPinned:
    """Pin the exact sig for paths with neither '|' nor backslash (issue #271 / ragmark#204).

    Stored keys are shared on disk, so these byte strings must never change.
    """

    @pytest.mark.parametrize(
        ("a", "b", "expected"),
        [
            ("a.md", "b.md", "weaklink|a.md|b.md"),
            ("b.md", "a.md", "weaklink|a.md|b.md"),
            ("docs/a.md", "refs/b.md", "weaklink|docs/a.md|refs/b.md"),
            (
                "My Notes/Daily Log.md",
                "Projects/Plan v2.md",
                "weaklink|My Notes/Daily Log.md|Projects/Plan v2.md",
            ),
            (
                "caf\u00e9/r\u00e9sum\u00e9.md",
                "\u65e5\u672c/\u30e1\u30e2.md",
                "weaklink|caf\u00e9/r\u00e9sum\u00e9.md|\u65e5\u672c/\u30e1\u30e2.md",
            ),
            ("a/b/c/d/deep.md", "a/b/shallow.md", "weaklink|a/b/c/d/deep.md|a/b/shallow.md"),
            ("same.md", "same.md", "weaklink|same.md|same.md"),
            ("notes/a-b_c.2026.md", "notes/A.md", "weaklink|notes/A.md|notes/a-b_c.2026.md"),
        ],
    )
    def test_ordinary_sig_is_byte_stable(self, a, b, expected):
        assert dismiss.weaklink_sig(a, b) == expected


class TestWeaklinkSigPipeFormatPinned:
    """Exact bytes for pairs where a path contains '|' (ragmark copies these bytes)."""

    @pytest.mark.parametrize(
        ("a", "b", "expected"),
        [
            ("x", "y|z", "weaklink2|x|y\\|z"),
            ("y|z", "x", "weaklink2|x|y\\|z"),
            ("x|y", "z", "weaklink2|x\\|y|z"),
            ("|", "x", "weaklink2|\\||x"),
            ("x", "|", "weaklink2|\\||x"),
            ("a|b", "c|d", "weaklink2|a\\|b|c\\|d"),
            ("x", "|\\", "weaklink2|\\|\\\\|x"),
        ],
    )
    def test_pipe_pair_bytes(self, a, b, expected):
        assert dismiss.weaklink_sig(a, b) == expected

    @pytest.mark.parametrize(
        ("a", "b", "expected"),
        [
            ("a\\b", "c", "weaklink|a\\b|c"),
            ("c", "a\\b", "weaklink|a\\b|c"),
            ("x\\", "y", "weaklink|x\\|y"),
            ("\\", "\\\\", "weaklink|\\|\\\\"),
        ],
    )
    def test_backslash_only_pair_keeps_legacy_format(self, a, b, expected):
        assert dismiss.weaklink_sig(a, b) == expected


def _strings(alphabet="a|\\", max_len=3):
    import itertools

    out = [""]
    for n in range(1, max_len + 1):
        out.extend("".join(t) for t in itertools.product(alphabet, repeat=n))
    return out


_TRICKY = _strings()


class TestWeaklinkSigInjective:
    def test_pipe_split_does_not_collide(self):
        assert dismiss.weaklink_sig("x", "y|z") != dismiss.weaklink_sig("x|y", "z")

    def test_backslash_escape_is_load_bearing(self):
        # Without escaping "\\" in the pipe format these two pairs would both join to
        # "weaklink2|\\|\\|x".
        assert dismiss.weaklink_sig("x", "|\\") != dismiss.weaklink_sig("|x", "\\")

    def test_order_independent(self):
        for a in _TRICKY:
            for b in _TRICKY:
                assert dismiss.weaklink_sig(a, b) == dismiss.weaklink_sig(b, a)

    def test_distinct_unordered_pairs_give_distinct_sigs(self):
        seen: dict[str, frozenset[str]] = {}
        for a in _TRICKY:
            for b in _TRICKY:
                pair = frozenset((a, b))
                sig = dismiss.weaklink_sig(a, b)
                assert seen.setdefault(sig, pair) == pair, (sig, seen[sig], pair)

    def test_pairs_without_a_pipe_use_the_legacy_format_exactly(self):
        for a in _TRICKY:
            for b in _TRICKY:
                if "|" in a or "|" in b:
                    continue
                assert dismiss.weaklink_sig(a, b) == "weaklink|" + "|".join(sorted([a, b]))

    def test_legacy_and_pipe_formats_are_disjoint(self):
        legacy, piped = set(), set()
        for a in _TRICKY:
            for b in _TRICKY:
                sig = dismiss.weaklink_sig(a, b)
                (piped if "|" in a or "|" in b else legacy).add(sig)
        assert legacy and piped
        assert legacy.isdisjoint(piped)
        assert all(s.startswith("weaklink|") for s in legacy)
        assert all(s.startswith("weaklink2|") for s in piped)


class TestPipePathDismissalRoundTrip:
    def _graph(self, names):
        from graphmark.graph import VaultGraph

        return VaultGraph(
            nodes={n: None for n in names},
            out_links={n: set() for n in names},
            back_links={n: set() for n in names},
        )

    def test_dismissing_one_pipe_pair_does_not_suppress_the_other(self, tmp_path):
        from graphmark.metrics import gaps

        for name in ("x", "y|z", "x|y", "z"):
            (tmp_path / name).write_text(f"content of {name}")
        graph = self._graph(["x", "y|z", "x|y", "z"])
        scores = {("x", "y|z"): 0.8, ("x|y", "z"): 0.8}

        def similar(rel, k):
            return [(o, s) for (r, o), s in scores.items() if r == rel]

        dismiss.record_dismissal(tmp_path, "x", "y|z")
        active = dismiss.active_dismissed_sigs(tmp_path)
        remaining = gaps(graph, similar, dismissed=active)
        assert [(g["a"], g["b"]) for g in remaining] == [("x|y", "z")]

    def test_legacy_unescaped_pipe_key_is_still_honoured(self, tmp_path):
        """A store written by the old encoding keys a pipe pair as 'weaklink|x|y|z'; the
        active sig is recomputed from the record's a/b, so it migrates to the new key."""
        (tmp_path / "x").write_text("x content")
        (tmp_path / "y|z").write_text("yz content")
        store = tmp_path / ".claude" / "data" / "connect-dismissed.json"
        store.parent.mkdir(parents=True)
        store.write_text(
            json.dumps(
                {
                    "weaklink|x|y|z": {
                        "a": "x",
                        "a_hash": dismiss.content_hash(tmp_path / "x"),
                        "b": "y|z",
                        "b_hash": dismiss.content_hash(tmp_path / "y|z"),
                    }
                }
            )
        )
        assert dismiss.active_dismissed_sigs(tmp_path) == {dismiss.weaklink_sig("x", "y|z")}


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

    def test_record_dismissal_survives_non_dict_json(self, tmp_path):
        (tmp_path / "x.md").write_text("x content")
        (tmp_path / "y.md").write_text("y content")
        store = tmp_path / dismiss._DEFAULT_PATH
        store.parent.mkdir(parents=True, exist_ok=True)
        store.write_text("[]")  # valid JSON, wrong shape
        dismiss.record_dismissal(tmp_path, "x.md", "y.md")
        sig = dismiss.weaklink_sig("x.md", "y.md")
        assert dismiss.load_dismissed(tmp_path) == {
            sig: {
                "a": "x.md",
                "a_hash": dismiss.content_hash(tmp_path / "x.md"),
                "b": "y.md",
                "b_hash": dismiss.content_hash(tmp_path / "y.md"),
            }
        }

    def test_record_missing_key_is_skipped_not_raised(self, tmp_path):
        """A record missing b_hash must be skipped, not raise, and must not hide a
        well-formed sibling record (#191)."""
        (tmp_path / "good.md").write_text("good content")
        (tmp_path / "good2.md").write_text("good2 content")
        (tmp_path / "bad_a.md").write_text("bad_a content")
        (tmp_path / "bad_b.md").write_text("bad_b content")
        good_sig = dismiss.weaklink_sig("good.md", "good2.md")
        bad_sig = dismiss.weaklink_sig("bad_a.md", "bad_b.md")
        store = tmp_path / dismiss._DEFAULT_PATH
        store.parent.mkdir(parents=True, exist_ok=True)
        store.write_text(
            json.dumps(
                {
                    good_sig: {
                        "a": "good.md",
                        "a_hash": dismiss.content_hash(tmp_path / "good.md"),
                        "b": "good2.md",
                        "b_hash": dismiss.content_hash(tmp_path / "good2.md"),
                    },
                    # "b_hash" deliberately missing — the other side (a/a_hash) is
                    # well-formed so a bare `record["b_hash"]` is actually reached.
                    bad_sig: {
                        "a": "bad_a.md",
                        "a_hash": dismiss.content_hash(tmp_path / "bad_a.md"),
                        "b": "bad_b.md",
                    },
                }
            )
        )
        assert dismiss.active_dismissed_sigs(tmp_path) == {good_sig}

    def test_record_non_string_value_is_skipped_not_raised(self, tmp_path):
        """A record where a value is non-string (e.g. None) must be skipped, not raise."""
        (tmp_path / "good.md").write_text("good content")
        (tmp_path / "good2.md").write_text("good2 content")
        (tmp_path / "otherb.md").write_text("otherb content")
        good_sig = dismiss.weaklink_sig("good.md", "good2.md")
        bad_sig = "weaklink|bad-non-string"
        store = tmp_path / dismiss._DEFAULT_PATH
        store.parent.mkdir(parents=True, exist_ok=True)
        store.write_text(
            json.dumps(
                {
                    good_sig: {
                        "a": "good.md",
                        "a_hash": dismiss.content_hash(tmp_path / "good.md"),
                        "b": "good2.md",
                        "b_hash": dismiss.content_hash(tmp_path / "good2.md"),
                    },
                    # "a" is None (non-string); "b"/"b_hash" are well-formed so a
                    # bare `root / record["a"]` is reached unconditionally.
                    bad_sig: {
                        "a": None,
                        "a_hash": "irrelevant",
                        "b": "otherb.md",
                        "b_hash": dismiss.content_hash(tmp_path / "otherb.md"),
                    },
                }
            )
        )
        assert dismiss.active_dismissed_sigs(tmp_path) == {good_sig}

    def test_record_empty_string_value_is_skipped_not_raised(self, tmp_path):
        """A record where a is "" must be skipped, not raise IsADirectoryError.

        root / "" evaluates to root itself (an existing directory), so a naive fix
        that only checks .exists() would crash in content_hash(). The other side
        (b/b_hash) is a well-formed real file so evaluation actually reaches the
        a-side check instead of short-circuiting on a broken b first.
        """
        (tmp_path / "good.md").write_text("good content")
        (tmp_path / "good2.md").write_text("good2 content")
        (tmp_path / "otherb.md").write_text("otherb content")
        good_sig = dismiss.weaklink_sig("good.md", "good2.md")
        bad_sig = "weaklink|bad-empty-string"
        store = tmp_path / dismiss._DEFAULT_PATH
        store.parent.mkdir(parents=True, exist_ok=True)
        store.write_text(
            json.dumps(
                {
                    good_sig: {
                        "a": "good.md",
                        "a_hash": dismiss.content_hash(tmp_path / "good.md"),
                        "b": "good2.md",
                        "b_hash": dismiss.content_hash(tmp_path / "good2.md"),
                    },
                    bad_sig: {
                        "a": "",
                        "a_hash": "irrelevant",
                        "b": "otherb.md",
                        "b_hash": dismiss.content_hash(tmp_path / "otherb.md"),
                    },
                }
            )
        )
        assert dismiss.active_dismissed_sigs(tmp_path) == {good_sig}

    def test_record_directory_value_is_skipped_not_raised(self, tmp_path):
        """A record naming a real directory other than the vault root must be
        skipped, not raise IsADirectoryError. The other side (b/b_hash) is a
        well-formed real file so evaluation actually reaches the a-side check.
        """
        (tmp_path / "good.md").write_text("good content")
        (tmp_path / "good2.md").write_text("good2 content")
        (tmp_path / "otherb.md").write_text("otherb content")
        (tmp_path / "some_subdir").mkdir()
        good_sig = dismiss.weaklink_sig("good.md", "good2.md")
        bad_sig = "weaklink|bad-directory-value"
        store = tmp_path / dismiss._DEFAULT_PATH
        store.parent.mkdir(parents=True, exist_ok=True)
        store.write_text(
            json.dumps(
                {
                    good_sig: {
                        "a": "good.md",
                        "a_hash": dismiss.content_hash(tmp_path / "good.md"),
                        "b": "good2.md",
                        "b_hash": dismiss.content_hash(tmp_path / "good2.md"),
                    },
                    bad_sig: {
                        "a": "some_subdir",
                        "a_hash": "irrelevant",
                        "b": "otherb.md",
                        "b_hash": dismiss.content_hash(tmp_path / "otherb.md"),
                    },
                }
            )
        )
        assert dismiss.active_dismissed_sigs(tmp_path) == {good_sig}

    def test_non_dict_entry_value_is_skipped_not_raised(self, tmp_path):
        """A store entry whose value is not a dict at all must be skipped, not raise."""
        (tmp_path / "good.md").write_text("good content")
        (tmp_path / "good2.md").write_text("good2 content")
        good_sig = dismiss.weaklink_sig("good.md", "good2.md")
        bad_sig = "weaklink|bad-non-dict-entry"
        store = tmp_path / dismiss._DEFAULT_PATH
        store.parent.mkdir(parents=True, exist_ok=True)
        store.write_text(
            json.dumps(
                {
                    good_sig: {
                        "a": "good.md",
                        "a_hash": dismiss.content_hash(tmp_path / "good.md"),
                        "b": "good2.md",
                        "b_hash": dismiss.content_hash(tmp_path / "good2.md"),
                    },
                    bad_sig: ["not", "a", "dict"],
                }
            )
        )
        assert dismiss.active_dismissed_sigs(tmp_path) == {good_sig}


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


class TestAtomicWriteInterruption:
    """A crash mid-write must not corrupt or wipe prior recorded dismissals (issue #257)."""

    def test_interrupted_write_preserves_prior_store_and_leaves_no_temp_file(
        self, tmp_path, monkeypatch
    ):
        (tmp_path / "x.md").write_text("x content")
        (tmp_path / "y.md").write_text("y content")
        (tmp_path / "z.md").write_text("z content")

        # First call: record a dismissal successfully, with no interference.
        dismiss.record_dismissal(tmp_path, "x.md", "y.md")
        store = tmp_path / dismiss._DEFAULT_PATH
        before = store.read_bytes()
        assert before  # sanity: the successful call actually wrote something

        real_write_text = Path.write_text

        def flaky_write_text(self, data, *args, **kwargs):
            # Simulate a write that is interrupted partway through: some bytes land on
            # disk (whatever file is being written at the time), then the process blows up.
            real_write_text(self, data[: len(data) // 2], *args, **kwargs)
            raise OSError("simulated interruption mid-write")

        monkeypatch.setattr(Path, "write_text", flaky_write_text)

        with pytest.raises(OSError):
            dismiss.record_dismissal(tmp_path, "x.md", "z.md")

        after = store.read_bytes()
        assert after == before, "the live store must be byte-identical to before the interruption"

        leftover = list(store.parent.glob(f"{store.name}.tmp*"))
        assert leftover == [], f"no <store>.tmp<pid> file should survive a failed write: {leftover}"


class TestRecordDismissalMissingNote:
    """A missing note under `root` must raise a clear ValueError, not a bare OS error (#208)."""

    def test_missing_a_raises_value_error_naming_path(self, tmp_path):
        (tmp_path / "y.md").write_text("y content")

        with pytest.raises(ValueError, match="note not found under"):
            dismiss.record_dismissal(tmp_path, "missing.md", "y.md")

    def test_missing_b_raises_value_error_naming_path(self, tmp_path):
        (tmp_path / "x.md").write_text("x content")

        with pytest.raises(ValueError, match="note not found under"):
            dismiss.record_dismissal(tmp_path, "x.md", "missing.md")

    def test_store_not_created_or_mutated_on_missing_note(self, tmp_path):
        (tmp_path / "x.md").write_text("x content")
        store = tmp_path / dismiss._DEFAULT_PATH

        with pytest.raises(ValueError):
            dismiss.record_dismissal(tmp_path, "x.md", "missing.md")

        assert not store.exists()
        assert not store.parent.exists()


class TestRecordDismissalContainment:
    """An `a`/`b` that resolves outside `root` (absolute path or `..` traversal) must be
    rejected before any hashing, mkdir, or write (#291)."""

    def test_rejects_absolute_a(self, tmp_path):
        (tmp_path / "y.md").write_text("y content")
        store = tmp_path / dismiss._DEFAULT_PATH

        with pytest.raises(ValueError, match="resolves outside"):
            dismiss.record_dismissal(tmp_path, "/etc/graphmark-291-does-not-exist", "y.md")

        assert not store.exists()
        assert not store.parent.exists()

    def test_rejects_absolute_b(self, tmp_path):
        (tmp_path / "x.md").write_text("x content")
        store = tmp_path / dismiss._DEFAULT_PATH

        with pytest.raises(ValueError, match="resolves outside"):
            dismiss.record_dismissal(tmp_path, "x.md", "/etc/graphmark-291-does-not-exist")

        assert not store.exists()
        assert not store.parent.exists()

    def test_rejects_traversal_a(self, tmp_path):
        (tmp_path / "y.md").write_text("y content")
        store = tmp_path / dismiss._DEFAULT_PATH
        # Enough "../" segments to actually escape tmp_path's nested pytest directory.
        traversal = os.path.join("..", "..", "graphmark-291-traversal-does-not-exist")

        with pytest.raises(ValueError, match="resolves outside"):
            dismiss.record_dismissal(tmp_path, traversal, "y.md")

        assert not store.exists()
        assert not store.parent.exists()

    def test_rejects_traversal_b(self, tmp_path):
        (tmp_path / "x.md").write_text("x content")
        store = tmp_path / dismiss._DEFAULT_PATH
        traversal = os.path.join("..", "..", "graphmark-291-traversal-does-not-exist")

        with pytest.raises(ValueError, match="resolves outside"):
            dismiss.record_dismissal(tmp_path, "x.md", traversal)

        assert not store.exists()
        assert not store.parent.exists()

    def test_well_formed_record_still_succeeds(self, tmp_path):
        """The containment guard must not reject ordinary in-vault paths (#291)."""
        (tmp_path / "x.md").write_text("x content")
        (tmp_path / "y.md").write_text("y content")

        dismiss.record_dismissal(tmp_path, "x.md", "y.md")

        sig = dismiss.weaklink_sig("x.md", "y.md")
        assert sig in dismiss.load_dismissed(tmp_path)


class TestActiveDismissedSigsContainment:
    """A stored record whose `a`/`b` resolves outside `root` must be treated as inactive
    (skipped, not raised), checked before `content_hash` is called on either path (#291).

    Each escaped record's hash fields use the REAL sha1 content hash of the escaped file,
    not a placeholder — otherwise the test can't tell the containment guard from an
    incidental hash mismatch that would produce the same "inactive" result on its own.
    """

    def test_skips_absolute_record(self, tmp_path):
        (tmp_path / "good.md").write_text("good content")
        (tmp_path / "good2.md").write_text("good2 content")
        (tmp_path / "otherb.md").write_text("otherb content")
        escaped = tmp_path.parent / "graphmark-291-escaped-absolute.md"
        escaped.write_text("real escaped content for absolute containment test")

        good_sig = dismiss.weaklink_sig("good.md", "good2.md")
        bad_sig = "weaklink|bad-absolute-a"
        store = tmp_path / dismiss._DEFAULT_PATH
        store.parent.mkdir(parents=True, exist_ok=True)
        store.write_text(
            json.dumps(
                {
                    good_sig: {
                        "a": "good.md",
                        "a_hash": dismiss.content_hash(tmp_path / "good.md"),
                        "b": "good2.md",
                        "b_hash": dismiss.content_hash(tmp_path / "good2.md"),
                    },
                    # "a" is an absolute path outside root; a_hash is the REAL hash of
                    # that escaped file so the containment guard is what's under test,
                    # not an incidental hash mismatch.
                    bad_sig: {
                        "a": str(escaped),
                        "a_hash": dismiss.content_hash(escaped),
                        "b": "otherb.md",
                        "b_hash": dismiss.content_hash(tmp_path / "otherb.md"),
                    },
                }
            )
        )

        try:
            assert dismiss.active_dismissed_sigs(tmp_path) == {good_sig}
        finally:
            escaped.unlink()

    def test_skips_traversal_record(self, tmp_path):
        (tmp_path / "good.md").write_text("good content")
        (tmp_path / "good2.md").write_text("good2 content")
        (tmp_path / "otherb.md").write_text("otherb content")
        # Two levels up: enough "../" segments to actually escape tmp_path, still inside
        # pytest's own writable tmp tree.
        escaped_dir = tmp_path.parent.parent
        escaped = escaped_dir / "graphmark-291-escaped-traversal.md"
        escaped.write_text("real escaped content for traversal containment test")
        traversal_rel = os.path.relpath(escaped, tmp_path)

        good_sig = dismiss.weaklink_sig("good.md", "good2.md")
        bad_sig = "weaklink|bad-traversal-a"
        store = tmp_path / dismiss._DEFAULT_PATH
        store.parent.mkdir(parents=True, exist_ok=True)
        store.write_text(
            json.dumps(
                {
                    good_sig: {
                        "a": "good.md",
                        "a_hash": dismiss.content_hash(tmp_path / "good.md"),
                        "b": "good2.md",
                        "b_hash": dismiss.content_hash(tmp_path / "good2.md"),
                    },
                    # "a" is a `..`-escaping relative path; a_hash is the REAL hash of
                    # that escaped file so the containment guard is what's under test.
                    bad_sig: {
                        "a": traversal_rel,
                        "a_hash": dismiss.content_hash(escaped),
                        "b": "otherb.md",
                        "b_hash": dismiss.content_hash(tmp_path / "otherb.md"),
                    },
                }
            )
        )

        try:
            assert dismiss.active_dismissed_sigs(tmp_path) == {good_sig}
        finally:
            escaped.unlink()

    def test_well_formed_records_still_active(self, tmp_path):
        """The containment guard must not exclude ordinary in-vault records (#291)."""
        (tmp_path / "x.md").write_text("x content")
        (tmp_path / "y.md").write_text("y content")
        dismiss.record_dismissal(tmp_path, "x.md", "y.md")

        sig = dismiss.weaklink_sig("x.md", "y.md")
        assert sig in dismiss.active_dismissed_sigs(tmp_path)
