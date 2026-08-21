"""Mechanical traversal layer: bounded, cheap, LLM-free.

Given similarity-weighted seeds, expand into a bounded candidate subgraph via spreading activation
(ACT-R style) or Personalized PageRank (HippoRAG style). Hub influence is normalized by out-degree.
An agent's LLM judgment (if any) runs *after* this, over the bounded result — never hop-by-hop.
"""

from __future__ import annotations


def _neighbors(store, node_id: str, primary_weight: float) -> list[tuple[str, float, str]]:
    """`(neighbor_id, weight, label)` over primary (parent/child) and secondary edges."""
    out: list[tuple[str, float, str]] = []
    for c in store.children(node_id):
        out.append((c.id, primary_weight, "child"))
    parent = store.get_parent(node_id)
    if parent:
        out.append((parent, primary_weight, "parent"))
    for e in store.edges_from(node_id):
        out.append((e.target_id, e.weight, "|".join(e.verb_tags) or "rel"))
    for e in store.edges_to(node_id):
        if not e.directed and e.source_id != node_id:   # undirected: also reachable backward
            out.append((e.source_id, e.weight, "|".join(e.verb_tags) or "rel"))
    for m in store.mounts_of(node_id):                  # mounts are hierarchy: hop both ways
        out.append((m.node_id, primary_weight, "mount"))
    for m in store.mounted_at(node_id):
        out.append((m.host_id, primary_weight, "mount"))
    return out


def spreading_activation(
    store,
    seeds: list[tuple[str, float]],
    *,
    max_hops: int = 3,
    decay: float = 0.6,
    threshold: float = 0.01,
    primary_weight: float = 0.5,
) -> tuple[dict[str, float], dict[str, tuple[str, str]]]:
    """Propagate activation from seeds. Returns `(activation, trace)` where trace maps each reached
    node to `(from_id, edge_label)` for explainability. Bounded by threshold + max_hops."""
    activation: dict[str, float] = {i: w for i, w in seeds}
    trace: dict[str, tuple[str, str]] = {i: ("seed", "seed") for i, _ in seeds}
    frontier: dict[str, float] = dict(activation)
    for hop in range(1, max_hops + 1):
        nxt: dict[str, float] = {}
        for u, a in frontier.items():
            nbrs = _neighbors(store, u, primary_weight)
            outdeg = len(nbrs) or 1                      # out-degree normalization (hub dampening)
            for v, w, label in nbrs:
                delta = a * (decay ** hop) * w / outdeg
                if delta < threshold:
                    continue
                activation[v] = activation.get(v, 0.0) + delta
                nxt[v] = nxt.get(v, 0.0) + delta
                trace.setdefault(v, (u, label))
        frontier = nxt
        if not frontier:
            break
    return activation, trace


def _reachable(store, seeds, max_hops, primary_weight):
    """Bounded node set + adjacency reachable within `max_hops` of the seeds."""
    nodes: set[str] = {i for i, _ in seeds}
    adj: dict[str, list[tuple[str, float]]] = {}
    frontier = set(nodes)
    for _ in range(max_hops):
        new: set[str] = set()
        for u in frontier:
            nbrs = _neighbors(store, u, primary_weight)
            adj[u] = [(v, w) for v, w, _ in nbrs]
            for v, _w in adj[u]:
                if v not in nodes:
                    new.add(v)
        nodes |= new
        frontier = new
        if not frontier:
            break
    return nodes, adj


def personalized_pagerank(
    store,
    seeds: list[tuple[str, float]],
    *,
    damping: float = 0.85,
    iters: int = 30,
    max_hops: int = 3,
    primary_weight: float = 0.5,
) -> dict[str, float]:
    """Random-walk-with-restart from similarity-weighted seeds over a bounded subgraph."""
    nodes, adj = _reachable(store, seeds, max_hops, primary_weight)
    total_seed = sum(w for _, w in seeds) or 1.0
    restart = {i: w / total_seed for i, w in seeds if i in nodes}
    rank: dict[str, float] = {n: restart.get(n, 0.0) for n in nodes}
    for _ in range(iters):
        nxt = {n: (1 - damping) * restart.get(n, 0.0) for n in nodes}
        for u in nodes:
            ru = rank.get(u, 0.0)
            if not ru:
                continue
            out = adj.get(u, [])
            tot = sum(w for _, w in out) or 1.0
            for v, w in out:
                if v in nxt:
                    nxt[v] += damping * ru * (w / tot)
        rank = nxt
    return rank
