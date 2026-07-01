"""Export helpers: JSON serialisation and Graphviz DOT output."""

from __future__ import annotations

import json

from graphmark.graph import VaultGraph


def to_json(obj) -> str:
    """Serialise any JSON-serialisable object to a string."""
    return json.dumps(obj)


def to_dot(graph: VaultGraph) -> str:
    """Emit a Graphviz digraph containing every node and directed edge."""
    lines = ["digraph G {"]
    for node in sorted(graph.nodes):
        lines.append(f'    "{node}";')
    for src in sorted(graph.out_links):
        for dst in sorted(graph.out_links[src]):
            lines.append(f'    "{src}" -> "{dst}";')
    lines.append("}")
    return "\n".join(lines)
