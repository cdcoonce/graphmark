"""Command-line interface for graphmark."""

from __future__ import annotations

import argparse
import sys
import tomllib
from pathlib import Path

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
    if args.config is None and args.root is None:
        print("error: --config or --root required", file=sys.stderr)
        sys.exit(1)

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
    parser = argparse.ArgumentParser(prog="graphmark")
    parser.add_argument("--config", metavar="PATH", help="TOML config file")
    parser.add_argument("--root", metavar="PATH", help="Vault root (overrides --config root)")

    sub = parser.add_subparsers(dest="command")

    sub.add_parser("stats")
    sub.add_parser("orphans")

    hubs_p = sub.add_parser("hubs")
    hubs_p.add_argument("--n", type=int, default=10)

    sub.add_parser("clusters")
    sub.add_parser("bridges")
    sub.add_parser("siloed")

    nb_p = sub.add_parser("neighborhood")
    nb_p.add_argument("--note", required=True)
    nb_p.add_argument("--depth", type=int, default=1)

    pr_p = sub.add_parser("pagerank")
    pr_p.add_argument("--n", type=int, default=10)
    pr_p.add_argument("--alpha", type=float, default=0.85)

    exp_p = sub.add_parser("export")
    exp_p.add_argument("format", choices=["dot"])

    sub.add_parser("gaps")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

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
        print(to_json(pagerank(graph, n=args.n, alpha=args.alpha)))
    elif args.command == "export" and args.format == "dot":
        print(to_dot(graph))


if __name__ == "__main__":
    main()
