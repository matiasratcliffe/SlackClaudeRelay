"""Budgeted context assembly: turn a query into a ranked subgraph + a rendered markdown blob.

Pipeline: entry points (embeddings) → mechanical traversal (activation or PPR) → rank → fill a
node budget → render. The result records the path (seed/edge) that led to each node, so retrieval is
explainable.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .embeddings import EmbeddingProvider, find_entry_points
from .traversal import personalized_pagerank, spreading_activation


@dataclass
class AssemblyResult:
    query: str
    node_ids: list[str]
    edges: list[tuple[str, str, str]]           # (source_id, target_id, verb)
    markdown: str
    path: dict[str, tuple[str, str]] = field(default_factory=dict)  # node_id -> (from_id, label)


def assemble(
    store,
    embedder: EmbeddingProvider,
    query: str,
    *,
    budget_nodes: int = 8,
    strategy: str = "activation",
    query_tags: list[str] | None = None,
) -> AssemblyResult:
    """Assemble up to `budget_nodes` most-relevant nodes for `query`. `strategy`: activation|ppr."""
    seeds = find_entry_points(store, embedder, query, query_tags=query_tags)
    if not seeds:
        return AssemblyResult(query, [], [], "_No entry points matched._")

    if strategy == "ppr":
        scores = personalized_pagerank(store, seeds)
        path: dict[str, tuple[str, str]] = {i: ("seed", "seed") for i, _ in seeds}
    else:
        scores, path = spreading_activation(store, seeds)

    ranked = sorted(scores.items(), key=lambda p: p[1], reverse=True)
    chosen = [i for i, _ in ranked[:budget_nodes]]
    chosen_set = set(chosen)

    edges = [(e.source_id, e.target_id, "|".join(e.verb_tags) or "rel")
             for e in store.current_edges()
             if e.source_id in chosen_set and e.target_id in chosen_set]

    return AssemblyResult(
        query=query,
        node_ids=chosen,
        edges=edges,
        markdown=_render(store, chosen, scores, path),
        path={i: path.get(i, ("?", "?")) for i in chosen},
    )


def _render(store, node_ids, scores, path) -> str:
    lines = ["# Assembled context", ""]
    for nid in node_ids:
        n = store.get_node(nid)
        if not n:
            continue
        via = path.get(nid, ("seed", "seed"))
        lines.append(f"## {n.title}  ·  _{n.type.value}_  (score {scores.get(nid, 0):.3f})")
        if via[0] != "seed":
            frm = store.get_node(via[0])
            lines.append(f"> via **{via[1]}** from _{frm.title if frm else via[0]}_")
        if n.summary:
            lines.append(n.summary)
        elif n.body:
            lines.append(n.body)
        out = store.edges_from(nid)
        if out:
            # surface each wormhole's tree distance so the judgment layer can weigh the hop
            links = ", ".join(
                f"[[{(store.get_node(e.target_id) or _Missing()).title}]]"
                f" ({'|'.join(e.verb_tags) or 'rel'}"
                f"{f', d{e.tree_distance}' if e.tree_distance is not None else ''})" for e in out)
            lines.append(f"_links:_ {links}")
        lines.append("")
    return "\n".join(lines)


class _Missing:
    title = "?"
