"""Export helpers: JSON serialisation and Graphviz DOT output."""

from __future__ import annotations

import json

from graphmark.graph import VaultGraph


def to_json(obj: object) -> str:
    """Serialise any JSON-serialisable object to a string."""
    return json.dumps(obj)


def _dot_quote(s: str) -> str:
    """Escape a string for use inside a double-quoted DOT identifier.

    Backslash must be escaped before the quote so an already-present ``\\`` is not
    double-counted. Paths without special characters are returned unchanged.
    """
    return s.replace("\\", "\\\\").replace('"', '\\"')


def to_dot(graph: VaultGraph) -> str:
    """Emit a Graphviz digraph containing every node and directed edge."""
    lines = ["digraph G {"]
    for node in sorted(graph.nodes):
        lines.append(f'    "{_dot_quote(node)}";')
    for src in sorted(graph.out_links):
        for dst in sorted(graph.out_links[src]):
            lines.append(f'    "{_dot_quote(src)}" -> "{_dot_quote(dst)}";')
    lines.append("}")
    return "\n".join(lines)
