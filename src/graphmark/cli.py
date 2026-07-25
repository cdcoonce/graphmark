"""Command-line interface for graphmark."""

from __future__ import annotations

import argparse
import sys
import tomllib
from pathlib import Path

import networkx as nx

from graphmark import __version__
from graphmark.check import breach_lines, run_check
from graphmark.config import VaultConfig, load_config
from graphmark.export import to_dot, to_json
from graphmark.graph import NormalizeResolver, VaultGraph
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
from graphmark.parse import WikilinkExtractor


def _load(args: argparse.Namespace) -> tuple[VaultGraph, VaultConfig]:
    root = Path(args.root) if args.root is not None else None
    try:
        if args.config is not None:
            # root_override is applied during the load, so a policy-only config (no root key)
            # paired with --root works instead of raising before the override could apply.
            config = load_config(Path(args.config), root_override=root)
        else:
            config = VaultConfig(root=root)
        graph = VaultGraph.build(config, WikilinkExtractor(), NormalizeResolver())
    except (OSError, tomllib.TOMLDecodeError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(2)
    return graph, config


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="graphmark",
        description=(
            "Deterministic knowledge-graph analysis for markdown / [[wikilink]] vaults. "
            "Each subcommand prints JSON to stdout; errors go to stderr."
        ),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--config", metavar="PATH", help="TOML config file")
    parser.add_argument("--root", metavar="PATH", help="Vault root (overrides --config root)")

    sub = parser.add_subparsers(dest="command", metavar="COMMAND")

    sub.add_parser("stats", help="Aggregate vault stats: notes, edges, orphans, clusters, density")
    sub.add_parser("orphans", help="Notes with no links in or out (degree 0)")

    hubs_p = sub.add_parser("hubs", help="Most-connected notes, by undirected degree")
    hubs_p.add_argument("--n", type=int, default=10, help="How many hubs to return (default: 10)")

    sub.add_parser("clusters", help="Connected components of the link graph, largest first")
    sub.add_parser("bridges", help="Articulation points: notes whose removal splits the graph")
    sub.add_parser("siloed", help="Notes reachable from the mainland only through one bridge")

    nb_p = sub.add_parser("neighborhood", help="Links in and out of one note")
    nb_p.add_argument("--note", required=True, help="Vault-relative path, e.g. brain/hub.md")
    nb_p.add_argument(
        "--depth", type=int, default=1, help="1 for direct links, 2 to add two-hop (default: 1)"
    )

    pr_p = sub.add_parser("pagerank", help="PageRank importance ranking over the link graph")
    pr_p.add_argument("--n", type=int, default=10, help="How many notes to return (default: 10)")
    pr_p.add_argument(
        "--alpha", type=float, default=0.85, help="Damping factor in (0, 1) (default: 0.85)"
    )

    exp_p = sub.add_parser("export", help="Export the graph in another format")
    exp_p.add_argument("format", choices=["dot"], help="Output format")

    sub.add_parser("gaps", help="Link-gap suggestions (library-only; see the README)")

    sub.add_parser(
        "check",
        help="Gate vault health against the config's [check] thresholds (exit 1 on breach)",
    )

    args = parser.parse_args()

    # Usage errors all exit 2, matching argparse's own convention (and leaving exit 1 free for
    # future domain-level outcomes such as a `check` threshold breach). Help for a missing
    # command goes to stderr so piping stdout never captures it as data.
    if args.command is None:
        parser.print_help(sys.stderr)
        sys.exit(2)

    if args.config is None and args.root is None:
        parser.error("--config or --root required")

    if args.command == "gaps":
        # gaps needs a caller-injected similarity source the CLI can't supply; it is
        # library-only. Signpost the library API rather than silently printing [].
        print(
            "gaps requires an injected similarity source; use the library API "
            "(graphmark.metrics.gaps) — see README",
            file=sys.stderr,
        )
        sys.exit(2)

    graph, config = _load(args)

    if args.command == "stats":
        print(to_json(stats(graph)))
    elif args.command == "orphans":
        print(to_json(orphans(graph, config)))
    elif args.command == "hubs":
        print(to_json(hubs(graph, n=args.n)))
    elif args.command == "clusters":
        print(to_json(clusters(graph)))
    elif args.command == "bridges":
        print(to_json(bridges(graph)))
    elif args.command == "siloed":
        print(to_json(siloed_notes(graph)))
    elif args.command == "neighborhood":
        try:
            result = neighborhood(graph, args.note, depth=args.depth)
        except ValueError as e:
            print(f"error: {e}", file=sys.stderr)
            sys.exit(2)
        print(to_json(result))
    elif args.command == "pagerank":
        try:
            result = pagerank(graph, n=args.n, alpha=args.alpha)
        except (ValueError, nx.PowerIterationFailedConvergence) as e:
            print(f"error: {e}", file=sys.stderr)
            sys.exit(2)
        print(to_json(result))
    elif args.command == "export" and args.format == "dot":
        print(to_dot(graph))
    elif args.command == "check":
        try:
            report = run_check(graph, config)
        except ValueError as e:
            # A misconfigured gate is a usage error (2), never a breach (1) — CI must be able
            # to tell "your vault is unhealthy" from "your config is wrong".
            print(f"error: {e}", file=sys.stderr)
            sys.exit(2)
        print(to_json(report))
        for line in breach_lines(report):
            print(line, file=sys.stderr)
        sys.exit(0 if report["pass"] else 1)


if __name__ == "__main__":
    main()
