"""graphmark check — the deterministic vault-health gate.

Contract under test:
  * exit 0 = every enforced threshold passes; exit 1 = at least one breach (reserved for
    breach ALONE, so CI can trust it); exit 2 = usage/config error, including a policy that
    enforces nothing (a gate with nothing to check must not report green).
  * stdout is exactly one line, the JSON report, byte-stable across runs.
  * stderr carries one human-readable line per breach; it never pollutes stdout.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from graphmark.check import run_check
from graphmark.config import CheckPolicy, VaultConfig, load_config
from graphmark.graph import NormalizeResolver, VaultGraph
from graphmark.parse import WikilinkExtractor

SIMPLE_DIR = Path(__file__).parent / "fixtures" / "simple"
# Measured on the simple fixture: 2 orphans, 1 unresolved link, 0 siloed notes.
SIMPLE_ORPHANS, SIMPLE_UNRESOLVED, SIMPLE_SILOED = 2, 1, 0


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
