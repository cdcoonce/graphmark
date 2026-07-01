"""Structural metrics computed over a VaultGraph.

All outputs reproduce the reference engine (brain_map.py) exactly — shape,
ordering, and tie-breaking are pinned by tests/fixtures/simple/expected.json.
"""

from __future__ import annotations

import networkx as nx

from graphmark.config import VaultConfig
from graphmark.graph import VaultGraph


def _undirected(graph: VaultGraph) -> nx.Graph:
    G: nx.Graph = nx.Graph()
    G.add_nodes_from(graph.nodes.keys())
    for src, targets in graph.out_links.items():
        for dst in targets:
            G.add_edge(src, dst)
    return G


def stats(graph: VaultGraph) -> dict:
    """Return aggregate vault stats matching the oracle schema."""
    G = _undirected(graph)
    notes = len(graph.nodes)
    edges = sum(len(v) for v in graph.out_links.values())
    n_orphans = sum(1 for n in G.nodes if G.degree(n) == 0)
    n_clusters = sum(1 for c in nx.connected_components(G) if len(c) > 1)
    density = round(edges / notes, 2) if notes > 0 else 0.0
    return {
        "notes": notes,
        "edges": edges,
        "orphans": n_orphans,
        "clusters": n_clusters,
        "density": density,
    }


def orphans(graph: VaultGraph, config: VaultConfig) -> list[str]:
    """Return degree-0 nodes, excluding those matching transient_prefixes, sorted."""
    G = _undirected(graph)
    result = []
    for node in G.nodes:
        if G.degree(node) != 0:
            continue
        if any(node.startswith(prefix) for prefix in config.transient_prefixes):
            continue
        result.append(node)
    return sorted(result)


def hubs(graph: VaultGraph, n: int = 10) -> list[list]:
    """Return top-n nodes by undirected degree (degree > 0), ties broken by path order."""
    G = _undirected(graph)
    degree_pairs = [(node, G.degree(node)) for node in G.nodes if G.degree(node) > 0]
    degree_pairs.sort(key=lambda x: (-x[1], x[0]))
    return [[path, degree] for path, degree in degree_pairs[:n]]


def clusters(graph: VaultGraph) -> list[list[str]]:
    """Return connected components with >1 node, size-desc, members sorted."""
    G = _undirected(graph)
    components = [sorted(c) for c in nx.connected_components(G) if len(c) > 1]
    components.sort(key=lambda c: -len(c))
    return components


def bridges(graph: VaultGraph) -> list[str]:
    """Return articulation points of the undirected graph, sorted."""
    G = _undirected(graph)
    return sorted(nx.articulation_points(G))


def neighborhood(graph: VaultGraph, note: str, depth: int = 1) -> dict:
    """Return out/back neighbors (and two_hop when depth>=2) for a note."""
    out = sorted(graph.out_links.get(note, set()))
    back = sorted(graph.back_links.get(note, set()))
    result: dict = {"note": note, "out": out, "back": back}
    if depth >= 2:
        one_hop = set(out) | set(back)
        two_hop: set[str] = set()
        for neighbor in one_hop:
            two_hop |= set(graph.out_links.get(neighbor, set()))
            two_hop |= set(graph.back_links.get(neighbor, set()))
        two_hop -= one_hop
        two_hop.discard(note)
        result["two_hop"] = sorted(two_hop)
    return result
