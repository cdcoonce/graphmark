"""Corpus CLI — wires the manifest, fetch, report, and diff pieces into one command.

Implements the "runs offline against a warm cache; a missing cache entry skips with a clear
message" requirement: ``report`` and ``diff`` never build a report for a vault whose cache entry
is absent, they print a skip message to stderr and move on.

This is a sibling harness module, not part of the graphmark engine, but follows
``graphmark/cli.py``'s exit-code convention (usage/config errors exit 2, domain outcome is 0/1)
and exception-handling style (catch the same set ``_load`` catches around a manifest load).
"""

from __future__ import annotations

import argparse
import sys
import tomllib
from pathlib import Path

from scripts.corpus import diff as diff_mod
from scripts.corpus import fetch as fetch_mod
from scripts.corpus import report as report_mod
from scripts.corpus.manifest import CorpusVault, load_manifest


def _load_manifest_or_none(path: str) -> list[CorpusVault] | None:
    """Load the manifest at ``path``, printing ``error: {e}`` and returning ``None`` on failure.

    Catches the same exception set ``graphmark/cli.py``'s ``_load`` catches around its config
    load: ``load_manifest`` itself only raises ``ValueError``, but a missing/unreadable path or
    malformed TOML surfaces as a bare ``OSError``/``tomllib.TOMLDecodeError`` first.
    """
    try:
        return load_manifest(Path(path))
    except (OSError, tomllib.TOMLDecodeError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return None


def _cmd_fetch(args: argparse.Namespace) -> int:
    vaults = _load_manifest_or_none(args.manifest)
    if vaults is None:
        return 2

    cache_root = Path(args.cache_root)
    for vault in vaults:
        fetch_mod.fetch_vault(vault, cache_root)
    return 0


def _cmd_report(args: argparse.Namespace) -> int:
    vaults = _load_manifest_or_none(args.manifest)
    if vaults is None:
        return 2

    cache_root = Path(args.cache_root)
    out_dir = Path(args.out_dir)
    for vault in vaults:
        if not (cache_root / vault.name).exists():
            print(f"skip {vault.name}: not fetched", file=sys.stderr)
            continue
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / f"{vault.name}.json").write_text(report_mod.report_json(vault, cache_root))
    return 0


def _cmd_diff(args: argparse.Namespace) -> int:
    vaults = _load_manifest_or_none(args.manifest)
    if vaults is None:
        return 2

    cache_root = Path(args.cache_root)
    expected_dir = Path(args.expected_dir)
    all_lines: list[str] = []
    for vault in vaults:
        if not (cache_root / vault.name).exists():
            print(f"skip {vault.name}: not fetched", file=sys.stderr)
            continue

        actual = report_mod.build_vault_report(vault, cache_root)
        try:
            expected = diff_mod.load_expected(expected_dir / f"{vault.name}.json")
        except ValueError as e:
            print(f"error: {e}", file=sys.stderr)
            return 2

        all_lines.extend(diff_mod.diff_reports(expected, actual))

    for line in all_lines:
        print(line)

    # Nothing to report (including the all-skipped case) is not drift.
    return 1 if all_lines else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="corpus-cli",
        description="Fetch, report on, and diff the pinned third-party corpus vaults.",
    )
    sub = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    fetch_p = sub.add_parser("fetch", help="Populate the local cache with every manifest vault")
    fetch_p.add_argument("--manifest", required=True, metavar="PATH")
    fetch_p.add_argument("--cache-root", required=True, metavar="PATH")

    report_p = sub.add_parser("report", help="Write a per-vault report for every cached vault")
    report_p.add_argument("--manifest", required=True, metavar="PATH")
    report_p.add_argument("--cache-root", required=True, metavar="PATH")
    report_p.add_argument("--out-dir", required=True, metavar="PATH")

    diff_p = sub.add_parser("diff", help="Diff cached vault reports against frozen expected ones")
    diff_p.add_argument("--manifest", required=True, metavar="PATH")
    diff_p.add_argument("--cache-root", required=True, metavar="PATH")
    diff_p.add_argument("--expected-dir", required=True, metavar="PATH")

    args = parser.parse_args(argv)

    if args.command == "fetch":
        return _cmd_fetch(args)
    if args.command == "report":
        return _cmd_report(args)
    return _cmd_diff(args)


if __name__ == "__main__":
    sys.exit(main())
