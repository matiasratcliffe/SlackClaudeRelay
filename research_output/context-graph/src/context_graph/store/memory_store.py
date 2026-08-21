"""Zero-dependency in-memory backend — the executable reference semantics for `StorageBackend`.

Keeps the tool runnable with no server. Vector search is brute-force cosine (fine for the demo/test
scale; the Neo4j backend uses a real HNSW index). A single re-entrant lock guards structural
integrity only; higher-level concurrency semantics live in `locking.LockManager`.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Iterable

from ..embeddings import cosine
from ..model import Node, SecondaryEdge
from .base import StorageBackend


class MemoryStore(StorageBackend):
    def __init__(self) -> None:
        self._nodes: dict[str, Node] = {}
        self._edges: dict[str, SecondaryEdge] = {}
        self._children: dict[str, set[str]] = {}
        self._lock = threading.RLock()

    # --- nodes ---
    def get_node(self, node_id):
        with self._lock:
            return self._nodes.get(node_id)

    def put_node(self, node: Node) -> None:
        with self._lock:
            old = self._nodes.get(node.id)
            if old and old.parent_id != node.parent_id:
                self._children.get(old.parent_id, set()).discard(node.id)
            self._nodes[node.id] = node
            if node.parent_id:
                self._children.setdefault(node.parent_id, set()).add(node.id)

    def delete_node(self, node_id: str) -> None:
        with self._lock:
            n = self._nodes.pop(node_id, None)
            if n and n.parent_id:
                self._children.get(n.parent_id, set()).discard(node_id)
            self._children.pop(node_id, None)

    def all_nodes(self) -> Iterable[Node]:
        with self._lock:
            return list(self._nodes.values())

    def children(self, parent_id: str) -> list[Node]:
        with self._lock:
            return [self._nodes[c] for c in self._children.get(parent_id, set()) if c in self._nodes]

    def ancestors(self, node_id: str) -> list[str]:
        with self._lock:
            path: list[str] = []
            cur = self._nodes.get(node_id)
            seen: set[str] = set()
            while cur and cur.parent_id and cur.parent_id not in seen:
                path.append(cur.parent_id)
                seen.add(cur.parent_id)
                cur = self._nodes.get(cur.parent_id)
            return list(reversed(path))

    # --- edges ---
    def get_edge(self, edge_id):
        with self._lock:
            return self._edges.get(edge_id)

    def put_edge(self, edge: SecondaryEdge) -> None:
        with self._lock:
            self._edges[edge.id] = edge

    def delete_edge(self, edge_id: str) -> None:
        with self._lock:
            self._edges.pop(edge_id, None)

    def edges_from(self, node_id, current_only=True):
        with self._lock:
            return [e for e in self._edges.values()
                    if e.source_id == node_id and (e.is_current or not current_only)]

    def edges_to(self, node_id, current_only=True):
        with self._lock:
            out = [e for e in self._edges.values()
                   if e.target_id == node_id and (e.is_current or not current_only)]
            # symmetric edges are traversable from either endpoint
            out += [e for e in self._edges.values()
                    if not e.directed and e.source_id == node_id and (e.is_current or not current_only)]
            return out

    def current_edges(self):
        with self._lock:
            return [e for e in self._edges.values() if e.is_current]

    # --- versioned update ---
    def cas_update(self, kind, obj_id, expected_version, changes):
        with self._lock:
            store = self._nodes if kind == "node" else self._edges
            obj = store.get(obj_id)
            if obj is None or obj.version != expected_version:
                return False
            for k, v in changes.items():
                setattr(obj, k, v)
            obj.version += 1
            if kind == "node":
                obj.updated_at = time.time()
            return True

    # --- vector search ---
    def vector_search(self, embedding, k, kind="node"):
        with self._lock:
            if kind == "node":
                pool = [(n.id, n.embedding) for n in self._nodes.values()]
            else:
                pool = [(e.id, e.edge_embedding) for e in self._edges.values() if e.is_current]
        scored = [(i, cosine(embedding, emb)) for i, emb in pool if emb]
        scored.sort(key=lambda p: p[1], reverse=True)
        return scored[:k]
