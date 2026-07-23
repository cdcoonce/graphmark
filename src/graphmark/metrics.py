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


def siloed_notes(graph: VaultGraph) -> list[str]:
    """Return notes reachable from the mainland only through a single articulation point.

    For each bridge b: remove b, find connected components sorted size-desc; every
    component except the largest (mainland) is an island. Collect all island nodes
    (including degree-0 orphans that become singleton islands). Return sorted unique list.
    """
    G = _undirected(graph)
    island_nodes: set[str] = set()
    for bridge in nx.articulation_points(G):
        H = G.copy()
        H.remove_node(bridge)
        components = sorted(nx.connected_components(H), key=lambda c: -len(c))
        for component in components[1:]:
            island_nodes.update(component)
    return sorted(island_nodes)


def pagerank(graph: VaultGraph, n: int = 10, alpha: float = 0.85) -> list[list]:
    """Pure-python power iteration PageRank (matches networkx _pagerank_python).

    Dangling nodes (no out-edges) redistribute mass uniformly across all nodes.
    Returns top-n [path, score] pairs sorted score-desc then path-asc.
    """
    nodes = list(graph.nodes.keys())
    N = len(nodes)
    if N == 0:
        return []

    out_links = {node: graph.out_links.get(node, set()) for node in nodes}
    dangling = [node for node in nodes if not out_links[node]]
    dangling_weight = 1.0 / N

    x: dict[str, float] = {node: 1.0 / N for node in nodes}

    for _ in range(100):
        xlast = x
        x = dict.fromkeys(xlast, 0.0)
        danglesum = alpha * sum(xlast[node] for node in dangling)

        for src in nodes:
            out = out_links[src]
            if out:
                share = alpha * xlast[src] / len(out)
                for dst in out:
                    x[dst] += share

        for node in nodes:
            x[node] += danglesum * dangling_weight + (1.0 - alpha) * dangling_weight

        err = sum(abs(x[node] - xlast[node]) for node in nodes)
        if err < N * 1e-6:
            break

    pairs = sorted(x.items(), key=lambda kv: (-kv[1], kv[0]))
    return [[path, score] for path, score in pairs[:n]]


def gaps(
    graph: VaultGraph,
    similar_fn,
    threshold: float = 0.0,
    k: int = 5,
    note: str | None = None,
    dismissed: set | frozenset = frozenset(),
    exclude_prefixes: tuple = (),
    max_score: float | None = None,
    hub_degree: int | None = None,
    targets: list | None = None,
) -> list[dict]:
    """Return link-gap suggestions ranked by novelty (non-hub, cross-folder, score-desc)."""
    if note is not None:
        target_list = [note]
    elif targets is not None:
        target_list = targets
    else:
        target_list = list(graph.nodes.keys())

    G = _undirected(graph)

    def _hub(r: str) -> bool:
        return hub_degree is not None and r in G and G.degree(r) >= hub_degree

    dedup_map: dict = {}

    for rel in target_list:
        if any(rel.startswith(p) for p in exclude_prefixes):
            continue

        linked = graph.out_links.get(rel, set()) | graph.back_links.get(rel, set())

        for other, score in similar_fn(rel, k):
            if other == rel:
                continue
            if other in linked:
                continue
            if score < threshold:
                continue
            if any(other.startswith(p) for p in exclude_prefixes):
                continue
            if max_score is not None and score > max_score:
                continue

            sig = "weaklink|" + "|".join(sorted([rel, other]))
            if sig in dismissed:
                continue

            key = frozenset({rel, other})
            if key not in dedup_map or score > dedup_map[key][2]:
                dedup_map[key] = (rel, other, score, sig)

    def _rank_key(item):
        a, b, score, _sig = item
        hubby = _hub(a) or _hub(b)
        cross = a.split("/", 1)[0] != b.split("/", 1)[0]
        return (hubby, not cross, -score, a, b)

    candidates = sorted(dedup_map.values(), key=_rank_key)
    return [{"a": a, "b": b, "score": round(s, 4), "sig": sig} for a, b, s, sig in candidates]


def neighborhood(graph: VaultGraph, note: str, depth: int = 1) -> dict:
    """Return out/back neighbors (and two_hop when depth>=2) for a note."""
    if note not in graph.nodes:
        raise ValueError(f"unknown note: {note}")
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
