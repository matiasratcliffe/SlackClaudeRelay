"""ContextGraph facade: ties storage + embeddings + locking into the ingest/query API.

Writes go through the lock manager, auto-embed, and stamp provenance. Edges dedup/reinforce instead
of duplicating; conflicting facts append-and-supersede by authority; a synchronous structural
heuristic flags candidate contradictions (LLM adjudication is out of scope).
"""

from __future__ import annotations

import time
from enum import IntEnum

from .assembly import AssemblyResult, assemble
from .embeddings import EmbeddingProvider, HashingEmbedder, cosine, find_entry_points
from .locking import LockManager
from .model import Node, NodeType, SecondaryEdge, ROOT_ID, validate_new_node
from .store.base import StorageBackend
from .store.memory_store import MemoryStore

# Verbs that admit at most one current object per subject → two objects = contradiction candidate.
DEFAULT_FUNCTIONAL_VERBS = {"reports_to", "born_in", "located_in", "manager_of", "married_to"}


class Authority(IntEnum):
    CHAINED_INFERENCE = 1
    DIRECT_INFERENCE = 2
    SYSTEM_OF_RECORD = 3
    USER_STATED = 4


class ContextGraph:
    def __init__(
        self,
        store: StorageBackend | None = None,
        embedder: EmbeddingProvider | None = None,
        *,
        agent_id: str = "default",
        locks: LockManager | None = None,
        functional_verbs: set[str] | None = None,
        dedup_threshold: float = 0.92,
    ) -> None:
        self.store = store or MemoryStore()
        self.embedder = embedder or HashingEmbedder()
        self.agent_id = agent_id
        self.locks = locks or LockManager(self.store)
        self.functional_verbs = functional_verbs or set(DEFAULT_FUNCTIONAL_VERBS)
        self.dedup_threshold = dedup_threshold

    # --- setup ---
    def ensure_root(self, title: str = "Context") -> Node:
        root = self.store.get_node(ROOT_ID)
        if root is None:
            root = Node(title=title, type=NodeType.ROOT, id=ROOT_ID, parent_id=None,
                        embedding=self.embedder.embed(title), owner_agent_id=self.agent_id)
            self.store.put_node(root)
        return root

    # --- ingest ---
    def add_node(self, title, *, type=NodeType.NOTE, body="", parent_id=ROOT_ID,
                 tags=None, authority=Authority.DIRECT_INFERENCE, source=None) -> Node:
        node = Node(title=title, type=type, body=body, parent_id=parent_id,
                    tags=list(tags or []), owner_agent_id=self.agent_id,
                    authority=int(authority), source=source)
        node.embedding = self.embedder.embed(f"{title}\n{body}")
        validate_new_node(node, lambda i: self.store.get_node(i) is not None)
        if parent_id:
            self.locks.acquire_write(self.agent_id, parent_id)
        try:
            self.store.put_node(node)
        finally:
            self.locks.release_all(self.agent_id)
        return node

    def link(self, source_id, target_id, *, verb_tags=None, weight=1.0, directed=True,
             authority=Authority.DIRECT_INFERENCE, source=None) -> SecondaryEdge:
        verbs = list(verb_tags or [])
        emb = self._embed_edge(source_id, target_id, verbs)
        existing = self._find_equivalent_edge(source_id, target_id, verbs, emb)
        if existing is not None:
            self.locks.retry(lambda: self.store.cas_update(
                "edge", existing.id, existing.version,
                {"weight": existing.weight + weight, "valid_from": time.time()}))
            return self.store.get_edge(existing.id)
        edge = SecondaryEdge(source_id=source_id, target_id=target_id, verb_tags=verbs,
                             directed=directed, weight=weight, edge_embedding=emb,
                             authority=int(authority), owner_agent_id=self.agent_id, source=source)
        self.store.put_edge(edge)
        return edge

    def supersede(self, old_edge_id: str, **new_edge_kwargs) -> SecondaryEdge:
        """Close the old edge (valid_to=now) and append a replacement — non-destructive history."""
        old = self.store.get_edge(old_edge_id)
        if old is None:
            raise ValueError(f"edge {old_edge_id!r} not found")
        self.locks.retry(lambda: self.store.cas_update(
            "edge", old.id, old.version, {"valid_to": time.time()}))
        return self.link(old.source_id, old.target_id, **new_edge_kwargs)

    # --- query ---
    def search(self, query: str, **kw) -> list[tuple[Node, float]]:
        seeds = find_entry_points(self.store, self.embedder, query, **kw)
        return [(self.store.get_node(i), w) for i, w in seeds if self.store.get_node(i)]

    def traverse(self, query: str, *, budget_nodes: int = 8, strategy: str = "activation",
                 query_tags=None) -> AssemblyResult:
        return assemble(self.store, self.embedder, query, budget_nodes=budget_nodes,
                        strategy=strategy, query_tags=query_tags)

    # --- hub rollup (D8) ---
    def recompute_hub_summaries(self, threshold: int = 3) -> list[str]:
        """Write a rolled-up `summary` on every node whose degree ≥ threshold (top relations first).

        Traversal reads a node's summary before its body, so hubs are entered summary-first. Returns
        the ids updated. (Regeneration cadence — debounced/background — is out of scope here.)
        """
        updated: list[str] = []
        for n in list(self.store.all_nodes()):
            out = self.store.edges_from(n.id)
            degree = len(out) + len(self.store.edges_to(n.id))
            if degree < threshold:
                continue
            rels = sorted(out, key=lambda e: e.weight, reverse=True)[:5]
            parts = [f"{'|'.join(e.verb_tags) or 'rel'}→"
                     f"{(self.store.get_node(e.target_id) or _M()).title}" for e in rels]
            summary = f"{n.title} — hub of {degree} relations: " + ", ".join(parts)
            if self.locks.retry(lambda n=n, s=summary:
                                self.store.cas_update("node", n.id, n.version, {"summary": s})):
                updated.append(n.id)
        return updated

    # --- integrity ---
    def contradictions(self) -> list[tuple[str, str, list[str]]]:
        """Candidate contradictions: `(source_id, functional_verb, [conflicting_target_ids])`."""
        by_key: dict[tuple[str, str], set[str]] = {}
        for e in self.store.current_edges():
            for v in e.verb_tags:
                if v in self.functional_verbs:
                    by_key.setdefault((e.source_id, v), set()).add(e.target_id)
        return [(src, verb, sorted(tgts)) for (src, verb), tgts in by_key.items() if len(tgts) > 1]

    # --- internals ---
    def _embed_edge(self, source_id, target_id, verbs) -> list[float]:
        s, t = self.store.get_node(source_id), self.store.get_node(target_id)
        text = " ".join(verbs + [s.title if s else "", t.title if t else ""])
        return self.embedder.embed(text)

    def _find_equivalent_edge(self, source_id, target_id, verbs, emb) -> SecondaryEdge | None:
        vset = set(verbs)
        for e in self.store.edges_from(source_id):
            if e.target_id != target_id:
                continue
            if (vset & set(e.verb_tags)) or (e.edge_embedding and cosine(emb, e.edge_embedding) >= self.dedup_threshold):
                return e
        return None


class _M:
    """Placeholder for a missing node (defensive rendering)."""
    title = "?"
