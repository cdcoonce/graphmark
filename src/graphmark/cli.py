"""Command-line interface for graphmark."""

from __future__ import annotations

import argparse
import os
import sys
import tomllib
from pathlib import Path

import networkx as nx

from graphmark import __version__, build
from graphmark.check import breach_lines, links_report, links_summary_line, run_check
from graphmark.config import VaultConfig, load_config
from graphmark.export import to_dot, to_json
from graphmark.graph import VaultGraph
from graphmark.metrics import (
    bridges,
    clusters,
    hubs,
    neighborhood,
    orphans,
    pagerank,
    siloed_notes,
    stats,
)


def _die(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)
    sys.exit(2)


def _load(args: argparse.Namespace) -> tuple[VaultGraph, VaultConfig]:
    root = Path(args.root) if args.root is not None else None
    try:
        if args.config is not None:
            # root_override is applied during the load, so a policy-only config (no root key)
            # paired with --root works instead of raising before the override could apply.
            config = load_config(Path(args.config), root_override=root)
        else:
            config = VaultConfig(root=root)
        graph = build(config)
    except (OSError, tomllib.TOMLDecodeError, ValueError) as e:
        _die(str(e))
    return graph, config


def _reconcile_globals(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    """Merge each global's leading and trailing occurrence into one value.

    ``--config``/``--root`` are attached to the top-level parser *and*, under a separate dest, to
    every subparser, so both ``graphmark --root X stats`` and ``graphmark stats --root X`` work.
    Trailing-option order is what every comparable CLI accepts and what a user types by reflex — and
    it is what the README documents, so before this the first command a new user copied errored.

    Repeats with the **same** value are harmless. Two different values are a usage error rather than
    a silent last-wins: guessing which one the user meant is exactly the kind of quiet wrong answer
    this tool exists not to give. Both options collect with ``action="append"``, so this covers a
    repeat *within* one position (``stats --root A --root B``) as well as one across the two —
    argparse's own last-wins would otherwise swallow the first silently.

    Values are compared after ``os.path.normpath`` — no ``resolve()``/``expanduser()``/symlink
    following — so a trailing slash or a redundant ``./``/``.`` segment doesn't turn the same path
    into a spurious conflict. A relative spelling and an absolute spelling of the same location are
    still distinct values here: resolving that equivalence would need cwd-/symlink-dependent
    behavior this deliberately does not do.
    """
    for name in ("config", "root"):
        after = f"{name}_after"
        # `after` is absent when no subcommand ran at all — argparse never reached a subparser.
        given = (getattr(args, name) or []) + (getattr(args, after, None) or [])
        distinct = sorted({os.path.normpath(v) for v in given})
        if len(distinct) > 1:
            parser.error(f"--{name} given more than once with conflicting values: {distinct}")
        # Normalization is for the comparison only: keep the value exactly as the user gave it.
        # normpath collapses ".." lexically, which is wrong across a symlink.
        setattr(args, name, given[0] if given else None)
        if hasattr(args, after):
            delattr(args, after)


def main() -> None:
    # Attached to every subparser under a distinct dest, then reconciled: argparse would otherwise
    # let the subparser's default (None) overwrite a value the top-level parser had already read.
    trailing_globals = argparse.ArgumentParser(add_help=False)
    trailing_globals.add_argument(
        "--config",
        metavar="PATH",
        dest="config_after",
        action="append",
        help="TOML config file",
    )
    trailing_globals.add_argument(
        "--root",
        metavar="PATH",
        dest="root_after",
        action="append",
        help="Vault root (overrides --config root)",
    )

    parser = argparse.ArgumentParser(
        prog="graphmark",
        description=(
            "Deterministic knowledge-graph analysis for markdown / [[wikilink]] vaults. "
            "Each subcommand prints JSON to stdout; errors go to stderr."
        ),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--config", metavar="PATH", action="append", help="TOML config file")
    parser.add_argument(
        "--root", metavar="PATH", action="append", help="Vault root (overrides --config root)"
    )

    sub = parser.add_subparsers(dest="command", metavar="COMMAND")

    sub.add_parser(
        "stats",
        parents=[trailing_globals],
        help="Aggregate vault stats: notes, edges, orphans, clusters, density",
    )
    sub.add_parser(
        "orphans", parents=[trailing_globals], help="Notes with no links in or out (degree 0)"
    )

    hubs_p = sub.add_parser(
        "hubs", parents=[trailing_globals], help="Most-connected notes, by undirected degree"
    )
    hubs_p.add_argument("--n", type=int, default=10, help="How many hubs to return (default: 10)")

    sub.add_parser(
        "clusters",
        parents=[trailing_globals],
        help="Connected components of the link graph, largest first",
    )
    sub.add_parser(
        "bridges",
        parents=[trailing_globals],
        help="Articulation points: notes whose removal splits the graph",
    )
    sub.add_parser(
        "siloed",
        parents=[trailing_globals],
        help="Notes reachable from the mainland only through one bridge",
    )

    nb_p = sub.add_parser(
        "neighborhood", parents=[trailing_globals], help="Links in and out of one note"
    )
    nb_p.add_argument("--note", required=True, help="Vault-relative path, e.g. brain/hub.md")
    nb_p.add_argument(
        "--depth", type=int, default=1, help="1 for direct links, 2 to add two-hop (default: 1)"
    )

    pr_p = sub.add_parser(
        "pagerank",
        parents=[trailing_globals],
        help="PageRank importance ranking over the link graph",
    )
    pr_p.add_argument("--n", type=int, default=10, help="How many notes to return (default: 10)")
    pr_p.add_argument(
        "--alpha", type=float, default=0.85, help="Damping factor in (0, 1) (default: 0.85)"
    )

    exp_p = sub.add_parser(
        "export", parents=[trailing_globals], help="Export the graph in another format"
    )
    exp_p.add_argument("format", choices=["dot"], help="Output format")

    sub.add_parser(
        "gaps",
        parents=[trailing_globals],
        help="Link-gap suggestions (library-only; see the README)",
    )

    sub.add_parser(
        "links",
        parents=[trailing_globals],
        help="How every wikilink was classified: counts per reason, plus alias resolutions",
    )

    sub.add_parser(
        "check",
        parents=[trailing_globals],
        help="Gate vault health against the config's [check] thresholds (exit 1 on breach)",
    )

    args = parser.parse_args()
    _reconcile_globals(parser, args)

    # Usage errors all exit 2, matching argparse's own convention (and leaving exit 1 free for
    # future domain-level outcomes such as a `check` threshold breach). Help for a missing
    # command goes to stderr so piping stdout never captures it as data.
    if args.command is None:
        parser.print_help(sys.stderr)
        sys.exit(2)

    if args.command == "gaps":
        # gaps needs a caller-injected similarity source the CLI can't supply; it is
        # library-only. Signpost the library API rather than silently printing []. This
        # must come before the --config/--root requirement below: gaps needs neither
        # flag, so a bare `graphmark gaps` should see this guidance, not the generic
        # usage error.
        print(
            "gaps requires an injected similarity source; use the library API "
            "(graphmark.metrics.gaps) — see README",
            file=sys.stderr,
        )
        sys.exit(2)

    if args.config is None and args.root is None:
        parser.error("--config or --root required")

    exit_code = 0  # what a closed stdout pipe exits with; `check` raises it to 1 on a breach
    try:
        graph, config = _load(args)

        if args.command == "stats":
            print(to_json(stats(graph)), flush=True)
        elif args.command == "orphans":
            print(to_json(orphans(graph, config)), flush=True)
        elif args.command == "hubs":
            try:
                result = hubs(graph, n=args.n)
            except ValueError as e:
                _die(str(e))
            print(to_json(result), flush=True)
        elif args.command == "clusters":
            print(to_json(clusters(graph)), flush=True)
        elif args.command == "bridges":
            print(to_json(bridges(graph)), flush=True)
        elif args.command == "siloed":
            print(to_json(siloed_notes(graph)), flush=True)
        elif args.command == "neighborhood":
            try:
                result = neighborhood(graph, args.note, depth=args.depth)
            except ValueError as e:
                _die(str(e))
            print(to_json(result), flush=True)
        elif args.command == "pagerank":
            try:
                result = pagerank(graph, n=args.n, alpha=args.alpha)
            except (ValueError, nx.PowerIterationFailedConvergence) as e:
                _die(str(e))
            print(to_json(result), flush=True)
        elif args.command == "export" and args.format == "dot":
            print(to_dot(graph), flush=True)
        elif args.command == "links":
            report = links_report(graph)
            print(to_json(report), flush=True)
            # stdout stays pipeable JSON; the at-a-glance line goes to stderr, as breach_lines does.
            print(links_summary_line(report), file=sys.stderr)
        elif args.command == "check":
            try:
                report = run_check(graph, config)
            except ValueError as e:
                # A misconfigured gate is a usage error (2), never a breach (1) — CI must be able
                # to tell "your vault is unhealthy" from "your config is wrong".
                _die(str(e))
            exit_code = 0 if report["pass"] else 1
            print(to_json(report), flush=True)
            for line in breach_lines(report):
                print(line, file=sys.stderr)
            sys.exit(exit_code)
    except BrokenPipeError:
        # The reader closed early. stdout is flushed per print so the error surfaces here, not at
        # interpreter shutdown (which would exit 120). Point stdout at devnull so that final flush
        # cannot raise again. The reader chose to stop, so that is a clean exit, except that a
        # `check` breach keeps its exit 1: CI must never see a breach as a pass.
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
        sys.exit(exit_code)


if __name__ == "__main__":
    main()
