"""`graphmark links` and the `links` block in `check` — Track F's visible surface.

Slice 1 made the classification countable; this makes it *readable*. The counts are worthless to a
vault owner sitting inside a Python object — the six-release alias defect was legible in the
distribution the whole time, and nobody could see it because no surface printed it.

Byte-stability is the contract, as it is for `check`: fixed key order, reasons in
`DIAGNOSIS_REASONS` order, so two runs over an unchanged vault diff to nothing.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from graphmark.check import links_report, run_check
from graphmark.config import VaultConfig
from graphmark.graph import DIAGNOSIS_REASONS, NormalizeResolver, VaultGraph
from graphmark.parse import WikilinkExtractor


def _write(root: Path, rel: str, text: str = "") -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build(root: Path, **kw) -> VaultGraph:
    return VaultGraph.build(VaultConfig(root=root, **kw), WikilinkExtractor(), NormalizeResolver())


def _vault(root: Path) -> None:
    _write(root, "hub.md", "[[target]] [[Nowhere]] [[#Local]] [[Chart.base]] [[Nickname]]\n")
    _write(root, "target.md")
    _write(root, "aliased.md", "---\naliases:\n  - Nickname\n---\n")


def _cli(*args: str) -> subprocess.CompletedProcess:
    """Global flags precede the subcommand — the form the parser actually accepts (see #130)."""
    return subprocess.run(
        [sys.executable, "-m", "graphmark.cli", *args], capture_output=True, text=True
    )


class TestLinksReport:
    def test_reports_total_counts_and_alias_resolved(self, tmp_path):
        _vault(tmp_path)
        report = links_report(_build(tmp_path))
        assert report["total"] == sum(report["counts"].values())
        assert report["counts"]["missing"] == 1
        assert report["counts"]["intra-note"] == 1
        assert report["counts"]["non-note-file"] == 1
        assert report["alias_resolved"] == 1

    def test_key_order_is_fixed(self, tmp_path):
        _vault(tmp_path)
        assert list(links_report(_build(tmp_path))) == ["total", "counts", "alias_resolved"]

    def test_reason_order_matches_diagnosis_reasons(self, tmp_path):
        _vault(tmp_path)
        assert tuple(links_report(_build(tmp_path))["counts"]) == DIAGNOSIS_REASONS

    def test_all_reasons_present_even_at_zero(self, tmp_path):
        _write(tmp_path, "a.md", "No links.\n")
        counts = links_report(_build(tmp_path))["counts"]
        assert set(counts) == set(DIAGNOSIS_REASONS)

    def test_a_directly_constructed_graph_still_reports_every_reason(self):
        # build() seeds all six keys, so a built graph never exercises the zero-fill. The public
        # constructor does: a graph assembled by hand carries an empty link_counts, and the report
        # must still be shaped like a report rather than silently losing its buckets.
        report = links_report(VaultGraph(nodes={}, out_links={}, back_links={}))
        assert tuple(report["counts"]) == DIAGNOSIS_REASONS
        assert report["total"] == 0

    def test_is_byte_stable_across_runs(self, tmp_path):
        _vault(tmp_path)
        first = json.dumps(links_report(_build(tmp_path)))
        second = json.dumps(links_report(_build(tmp_path)))
        assert first == second

    def test_an_empty_vault_reports_zeroes_not_an_error(self, tmp_path):
        vault = tmp_path / "empty"
        vault.mkdir()
        report = links_report(_build(vault))
        assert report["total"] == 0
        assert report["alias_resolved"] == 0


class TestCheckCarriesLinks:
    def test_check_report_includes_the_links_block(self, tmp_path):
        _vault(tmp_path)
        cfg = VaultConfig(root=tmp_path, check=_policy(max_orphans=99))
        report = run_check(_build(tmp_path), cfg)
        assert report["links"] == links_report(_build(tmp_path))

    def test_existing_keys_and_their_order_are_unchanged(self, tmp_path):
        # Consumers already parse this report; `links` is appended, never interleaved.
        _vault(tmp_path)
        cfg = VaultConfig(root=tmp_path, check=_policy(max_orphans=99))
        keys = list(run_check(_build(tmp_path), cfg))
        assert keys[:2] == ["pass", "checks"]
        assert keys == ["pass", "checks", "links"]

    def test_the_verdict_is_unaffected_by_the_addition(self, tmp_path):
        # A heuristic block must never be able to fail someone's build.
        _vault(tmp_path)
        passing = run_check(
            _build(tmp_path), VaultConfig(root=tmp_path, check=_policy(max_orphans=99))
        )
        # The vault has one `missing` link, so this threshold genuinely breaches.
        failing = run_check(
            _build(tmp_path), VaultConfig(root=tmp_path, check=_policy(max_unresolved_links=0))
        )
        assert passing["pass"] is True
        assert failing["pass"] is False
        assert passing["links"] == failing["links"]


def _policy(**kw):
    from graphmark.config import CheckPolicy

    return CheckPolicy(**kw)


class TestCli:
    def test_links_subcommand_emits_the_report(self, tmp_path):
        _vault(tmp_path)
        proc = _cli("--root", str(tmp_path), "links")
        assert proc.returncode == 0
        assert json.loads(proc.stdout) == links_report(_build(tmp_path))

    def test_stdout_is_pure_json(self, tmp_path):
        # stdout must stay pipeable; the human-readable summary belongs on stderr.
        _vault(tmp_path)
        proc = _cli("--root", str(tmp_path), "links")
        json.loads(proc.stdout)
        assert proc.stdout.count("\n") == 1

    def test_a_human_readable_summary_goes_to_stderr(self, tmp_path):
        _vault(tmp_path)
        proc = _cli("--root", str(tmp_path), "links")
        assert "resolved" in proc.stderr
        assert "alias-resolved" in proc.stderr

    def test_requires_a_root_or_config(self, tmp_path):
        proc = _cli("links")
        assert proc.returncode == 2

    def test_a_bad_root_is_a_usage_error(self, tmp_path):
        proc = _cli("--root", str(tmp_path / "nope"), "links")
        assert proc.returncode == 2
        assert "error:" in proc.stderr

    def test_check_output_carries_links_through_the_cli(self, tmp_path):
        _vault(tmp_path)
        cfg = tmp_path / "v.toml"
        cfg.write_text(f'root = "{tmp_path}"\n\n[check]\nmax_orphans = 99\n', encoding="utf-8")
        proc = _cli("--config", str(cfg), "check")
        assert proc.returncode == 0
        assert "links" in json.loads(proc.stdout)

    @pytest.mark.parametrize("flag", ["-h", "--help"])
    def test_links_has_help_text(self, tmp_path, flag):
        proc = _cli("links", flag)
        assert proc.returncode == 0
        assert "links" in proc.stdout.lower()
