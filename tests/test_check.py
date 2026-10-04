"""graphmark check — the deterministic vault-health gate.

Contract under test:
  * exit 0 = every enforced threshold passes; exit 1 = at least one breach (reserved for
    breach ALONE, so CI can trust it); exit 2 = usage/config error, including a policy that
    enforces nothing (a gate with nothing to check must not report green).
  * stdout is exactly one line, the JSON report, byte-stable across runs.
  * stderr carries one human-readable line per breach; it never pollutes stdout.
"""

from __future__ import annotations

import dataclasses
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from graphmark.check import _DISPATCH, breach_lines, links_report, run_check, unresolved_link_count
from graphmark.config import CheckPolicy, VaultConfig, load_config
from graphmark.graph import NormalizeResolver, VaultGraph
from graphmark.parse import WikilinkExtractor

SIMPLE_DIR = Path(__file__).parent / "fixtures" / "simple"
# Measured on the simple fixture: 2 orphans, 1 unresolved link, 0 siloed notes.
SIMPLE_ORPHANS, SIMPLE_UNRESOLVED, SIMPLE_SILOED = 2, 1, 0

# The alt fixture has 5 siloed notes (tests/fixtures/alt/expected.json), unlike the simple
# fixture above where SIMPLE_SILOED == 0 — it's the only fixture that can drive max_siloed's
# breach arm without inventing a new one (issue #241).
ALT_DIR = Path(__file__).parent / "fixtures" / "alt"


def _graph_and_config(**check_kwargs) -> tuple[VaultGraph, VaultConfig]:
    config = load_config(SIMPLE_DIR / "config.toml")
    config.check = CheckPolicy(**check_kwargs)
    graph = VaultGraph.build(config, WikilinkExtractor(), NormalizeResolver())
    return graph, config


def _toml(tmp_path, block: str) -> Path:
    toml = tmp_path / "vault.toml"
    toml.write_text(f'root = "{SIMPLE_DIR / "vault"}"\n{block}')
    return toml


def _run(argv, capsys, expect_code):
    from graphmark.cli import main

    with patch.object(sys, "argv", argv), pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == expect_code, f"expected exit {expect_code}, got {exc.value.code}"
    captured = capsys.readouterr()
    return captured.out, captured.err


class TestReportShape:
    def test_only_enforced_thresholds_appear(self):
        graph, config = _graph_and_config(max_orphans=5)
        report = run_check(graph, config)
        assert [c["name"] for c in report["checks"]] == ["max_orphans"]

    def test_checks_follow_checkpolicy_field_order(self):
        graph, config = _graph_and_config(max_siloed=1, max_orphans=5, max_unresolved_links=2)
        report = run_check(graph, config)
        assert [c["name"] for c in report["checks"]] == [
            "max_orphans",
            "max_unresolved_links",
            "max_siloed",
        ]

    def test_each_check_reports_limit_and_actual(self):
        graph, config = _graph_and_config(max_orphans=5)
        (check,) = run_check(graph, config)["checks"]
        assert check == {"name": "max_orphans", "limit": 5, "actual": SIMPLE_ORPHANS, "pass": True}

    def test_counts_match_the_metrics(self):
        graph, config = _graph_and_config(max_orphans=99, max_unresolved_links=99, max_siloed=99)
        actual = {c["name"]: c["actual"] for c in run_check(graph, config)["checks"]}
        assert actual == {
            "max_orphans": SIMPLE_ORPHANS,
            "max_unresolved_links": SIMPLE_UNRESOLVED,
            "max_siloed": SIMPLE_SILOED,
        }

    def test_top_level_pass_is_the_conjunction(self):
        graph, config = _graph_and_config(max_orphans=SIMPLE_ORPHANS, max_unresolved_links=0)
        report = run_check(graph, config)
        assert report["pass"] is False  # orphans pass, unresolved breaches


class TestThresholdSemantics:
    def test_actual_equal_to_limit_passes(self):
        # "max" is inclusive: exactly at the limit is acceptable.
        graph, config = _graph_and_config(max_orphans=SIMPLE_ORPHANS)
        assert run_check(graph, config)["pass"] is True

    def test_one_over_the_limit_breaches(self):
        graph, config = _graph_and_config(max_orphans=SIMPLE_ORPHANS - 1)
        assert run_check(graph, config)["pass"] is False

    def test_zero_limit_with_zero_actual_passes(self):
        graph, config = _graph_and_config(max_siloed=0)
        assert run_check(graph, config)["pass"] is True

    def test_unconfigured_policy_raises(self):
        graph, config = _graph_and_config()
        with pytest.raises(ValueError, match="no \\[check\\] policy"):
            run_check(graph, config)


class TestUnconfiguredMessageIsDerived:
    def test_message_names_a_field_that_does_not_exist_on_real_checkpolicy(self):
        # A hardcoded message can never contain a name it doesn't already know about, so this
        # only goes green when the threshold list is truly built from fields(config.check)
        # rather than a literal string that happens to match today's three real names.
        @dataclasses.dataclass(frozen=True)
        class _FakePolicy:
            not_a_real_threshold: int | None = None

            def is_configured(self) -> bool:
                return False

        graph, config = _graph_and_config()
        config.check = _FakePolicy()
        with pytest.raises(ValueError, match="not_a_real_threshold"):
            run_check(graph, config)

    def test_message_text_is_unchanged_for_the_real_checkpolicy(self):
        # Deriving the list must not change today's user-facing text by a single byte.
        graph, config = _graph_and_config()
        with pytest.raises(ValueError) as exc_info:
            run_check(graph, config)
        assert str(exc_info.value) == (
            "no [check] policy configured: set at least one threshold in the config's [check] "
            "table (max_orphans, max_unresolved_links, max_siloed)"
        )


class TestByteStability:
    """The report must diff cleanly across runs — pinned against a literal."""

    # The `links` block is appended after `checks`, so existing consumers keep parsing what they
    # already parsed. Note the cross-check the literal now pins: max_unresolved_links' actual (1)
    # equals counts.missing (1) — the gate's flagship number and the distribution behind it cannot
    # silently disagree.
    EXPECTED = (
        '{"pass": false, "checks": ['
        '{"name": "max_orphans", "limit": 1, "actual": 2, "pass": false}, '
        '{"name": "max_unresolved_links", "limit": 0, "actual": 1, "pass": false}, '
        '{"name": "max_siloed", "limit": 0, "actual": 0, "pass": true}], '
        '"links": {"total": 7, "counts": {"resolved": 6, "ambiguous": 0, "non-note-file": 0, '
        '"out-of-scope-note": 0, "missing": 1, "intra-note": 0}, "alias_resolved": 0}}'
    )

    def test_cli_report_is_byte_identical_to_the_oracle(self, tmp_path, capsys):
        toml = _toml(
            tmp_path,
            "[check]\nmax_orphans = 1\nmax_unresolved_links = 0\nmax_siloed = 0\n",
        )
        out, _ = _run(["graphmark", "--config", str(toml), "check"], capsys, 1)
        assert out == self.EXPECTED + "\n"

    def test_repeated_runs_are_identical(self, tmp_path, capsys):
        toml = _toml(tmp_path, "[check]\nmax_orphans = 1\nmax_unresolved_links = 0\n")
        first, _ = _run(["graphmark", "--config", str(toml), "check"], capsys, 1)
        second, _ = _run(["graphmark", "--config", str(toml), "check"], capsys, 1)
        assert first == second

    def test_stdout_is_exactly_one_line(self, tmp_path, capsys):
        toml = _toml(tmp_path, "[check]\nmax_orphans = 99\n")
        out, _ = _run(["graphmark", "--config", str(toml), "check"], capsys, 0)
        assert out.count("\n") == 1


class TestExitCodes:
    def test_all_pass_exits_0(self, tmp_path, capsys):
        toml = _toml(tmp_path, "[check]\nmax_orphans = 99\nmax_unresolved_links = 99\n")
        out, err = _run(["graphmark", "--config", str(toml), "check"], capsys, 0)
        assert json.loads(out)["pass"] is True
        assert err == ""

    def test_breach_exits_1(self, tmp_path, capsys):
        toml = _toml(tmp_path, "[check]\nmax_orphans = 0\n")
        out, err = _run(["graphmark", "--config", str(toml), "check"], capsys, 1)
        assert json.loads(out)["pass"] is False
        assert "max_orphans" in err

    def test_stderr_names_every_breach(self, tmp_path, capsys):
        toml = _toml(tmp_path, "[check]\nmax_orphans = 0\nmax_unresolved_links = 0\n")
        _, err = _run(["graphmark", "--config", str(toml), "check"], capsys, 1)
        assert "max_orphans" in err
        assert "max_unresolved_links" in err
        assert len(err.strip().splitlines()) == 2

    def test_unconfigured_policy_exits_2_not_0(self, tmp_path, capsys):
        # The critical case: a gate with nothing to check must NOT report green.
        toml = _toml(tmp_path, "")
        out, err = _run(["graphmark", "--config", str(toml), "check"], capsys, 2)
        assert out == ""
        assert "policy" in err

    def test_typo_in_check_block_exits_2(self, tmp_path, capsys):
        toml = _toml(tmp_path, "[check]\nmax_orphan = 1\n")
        out, err = _run(["graphmark", "--config", str(toml), "check"], capsys, 2)
        assert out == ""
        assert "max_orphan" in err

    def test_bad_vault_root_exits_2_not_1(self, tmp_path, capsys):
        # A wrong path must be distinguishable from a real breach.
        toml = tmp_path / "bad.toml"
        toml.write_text(f'root = "{tmp_path / "nope"}"\n[check]\nmax_orphans = 0\n')
        out, err = _run(["graphmark", "--config", str(toml), "check"], capsys, 2)
        assert out == ""
        assert "root" in err

    def test_root_only_without_a_config_exits_2(self, capsys):
        # --root alone cannot carry a [check] policy, so there is nothing to enforce.
        argv = ["graphmark", "--root", str(SIMPLE_DIR / "vault"), "check"]
        out, err = _run(argv, capsys, 2)
        assert out == ""
        assert "policy" in err


class TestUnresolvedLinkCountTransientPrefixes:
    """unresolved_link_count honors transient_prefixes when a config is given (issue #256).

    A tiny synthetic vault (not a frozen fixture) with one broken link inside a
    transient_prefixes-matched note and one identical-shape broken link outside it.
    """

    @staticmethod
    def _build(tmp_path) -> tuple[VaultGraph, VaultConfig]:
        (tmp_path / "daily").mkdir()
        (tmp_path / "daily" / "scratch.md").write_text("Broken: [[NopeMissing]]\n")
        (tmp_path / "normal.md").write_text("Broken: [[AlsoMissing]]\n")
        config = VaultConfig(root=tmp_path, transient_prefixes=("daily/",))
        graph = VaultGraph.build(config, WikilinkExtractor(), NormalizeResolver())
        return graph, config

    def test_no_config_counts_every_occurrence(self, tmp_path):
        graph, _ = self._build(tmp_path)
        assert unresolved_link_count(graph) == 2

    def test_config_none_counts_every_occurrence(self, tmp_path):
        graph, _ = self._build(tmp_path)
        assert unresolved_link_count(graph, config=None) == 2

    def test_config_given_excludes_transient_prefix_matches(self, tmp_path):
        graph, config = self._build(tmp_path)
        assert unresolved_link_count(graph, config=config) == 1

    def test_run_check_passes_config_through_to_max_unresolved_links(self, tmp_path):
        graph, config = self._build(tmp_path)
        config.check = CheckPolicy(max_unresolved_links=1)
        (check,) = run_check(graph, config)["checks"]
        assert check == {
            "name": "max_unresolved_links",
            "limit": 1,
            "actual": 1,
            "pass": True,
        }


class TestMaxUnresolvedLinksCombinesAmbiguousAndMissing:
    """run_check's max_unresolved_links dispatch must count both broken-link reasons, not just
    `missing` (issue #251). `unresolved_link_count`'s combination of `ambiguous` + `missing` is
    already proven at that function's own level (test_diagnose.py, test_link_counts.py — see
    #237, closed as already covered); the residual gap #251 targets is that no existing
    `run_check` test in this file drives a vault containing both reasons at once — every one
    uses either the SIMPLE fixture (0 ambiguous, 1 missing) or a synthetic vault with only
    `missing` links (TestUnresolvedLinkCountTransientPrefixes above).
    """

    @staticmethod
    def _build(tmp_path) -> tuple[VaultGraph, VaultConfig]:
        # Two same-basename notes make "[[note]]" ambiguous; "[[Nowhere]]" has no target at all,
        # making it missing — the same construction as
        # test_link_counts.py::TestConservationLaw::test_unresolved_equals_ambiguous_plus_missing.
        (tmp_path / "one").mkdir()
        (tmp_path / "two").mkdir()
        (tmp_path / "one" / "note.md").write_text("Hub note.\n")
        (tmp_path / "two" / "note.md").write_text("Hub note.\n")
        (tmp_path / "hub.md").write_text("[[note]] [[Nowhere]]\n")
        config = VaultConfig(root=tmp_path)
        graph = VaultGraph.build(config, WikilinkExtractor(), NormalizeResolver())
        return graph, config

    def test_run_check_actual_is_ambiguous_plus_missing(self, tmp_path):
        graph, config = self._build(tmp_path)
        config.check = CheckPolicy(max_unresolved_links=99)
        counts = links_report(graph)["counts"]
        # Both reasons must actually be present, or this test would not distinguish a dispatch
        # that dropped one of them from one that didn't.
        assert counts["ambiguous"] > 0
        assert counts["missing"] > 0

        (check,) = run_check(graph, config)["checks"]

        assert check["actual"] == counts["ambiguous"] + counts["missing"]
        assert check["actual"] > counts["ambiguous"]
        assert check["actual"] > counts["missing"]


class TestMaxSiloedBreach:
    """max_siloed's breach arm, unlike max_orphans and max_unresolved_links, had zero coverage:
    every existing max_siloed-parameterized test runs against the simple fixture, where
    SIMPLE_SILOED == 0, so `_actual("max_siloed", ...)` was never driven past its configured
    limit (issue #241). The alt fixture's 5 siloed notes make that reachable.
    """

    def test_max_siloed_breach_is_reported_and_named(self):
        config = load_config(ALT_DIR / "config.toml")
        config.check = CheckPolicy(max_siloed=2)
        graph = VaultGraph.build(config, WikilinkExtractor(), NormalizeResolver())
        report = run_check(graph, config)
        (check,) = report["checks"]
        assert check == {"name": "max_siloed", "limit": 2, "actual": 5, "pass": False}
        assert report["pass"] is False
        assert any(line.startswith("max_siloed") for line in breach_lines(report))


class TestDispatchMappingWired:
    """_DISPATCH must have an entry for every CheckPolicy field (issue #234).

    A future field added to CheckPolicy without a matching _DISPATCH entry must fail this test
    at test time, rather than only failing at first real invocation via run_check's KeyError.
    """

    def test_dispatch_keys_match_checkpolicy_fields(self):
        assert set(_DISPATCH) == {f.name for f in dataclasses.fields(CheckPolicy)}


class TestBreachLines:
    """Direct unit tests for `breach_lines` (issue #272) — no CLI subprocess, no real graph.

    Coverage before this class was entirely indirect (loose substring assertions against CLI
    stderr in TestExitCodes/TestMaxSiloedBreach above); nothing pinned the exact
    ``f"{name}: {actual} exceeds limit {limit}"`` format or that passing checks are omitted.
    """

    def test_all_passing_report_yields_empty_list(self):
        report = {
            "checks": [
                {"name": "max_orphans", "limit": 5, "actual": 2, "pass": True},
                {"name": "max_siloed", "limit": 0, "actual": 0, "pass": True},
            ]
        }
        assert breach_lines(report) == []

    def test_single_breach_exact_format(self):
        report = {"checks": [{"name": "max_orphans", "limit": 1, "actual": 3, "pass": False}]}
        assert breach_lines(report) == ["max_orphans: 3 exceeds limit 1"]

    def test_multiple_breaches_are_in_report_order_with_passing_checks_omitted(self):
        report = {
            "checks": [
                {"name": "max_orphans", "limit": 1, "actual": 3, "pass": False},
                {"name": "max_unresolved_links", "limit": 0, "actual": 0, "pass": True},
                {"name": "max_siloed", "limit": 2, "actual": 5, "pass": False},
            ]
        }
        assert breach_lines(report) == [
            "max_orphans: 3 exceeds limit 1",
            "max_siloed: 5 exceeds limit 2",
        ]
