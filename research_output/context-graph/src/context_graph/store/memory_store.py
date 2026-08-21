"""Zero-dependency in-memory backend — the executable reference semantics for `StorageBackend`.

Keeps the tool runnable with no server. Vector search is brute-force cosine (fine for the demo/test
scale; the Neo4j backend uses a real HNSW index). A single re-entrant lock guards structural
integrity only; higher-level concurrency semantics live in `locking.LockManager`.

Objects are **copied on read and write** so a caller's handle can never mutate stored state behind
the store's back — mirroring the detached-copy behaviour of a real database and making version/CAS
meaningful.
"""

from __future__ import annotations

import copy
import json
import threading
import time
from collections.abc import Iterable
from dataclasses import asdict
from pathlib import Path

from ..embeddings import cosine
from ..model import MountLink, Node, NodeType, SecondaryEdge
from .base import StorageBackend

_cp = copy.deepcopy


class MemoryStore(StorageBackend):
    def __init__(self) -> None:
        self._nodes: dict[str, Node] = {}
        self._edges: dict[str, SecondaryEdge] = {}
        self._mounts: dict[str, MountLink] = {}
        self._children: dict[str, set[str]] = {}
        self._lock = threading.RLock()

    # --- nodes ---
    def get_node(self, node_id):
        with self._lock:
            n = self._nodes.get(node_id)
            return _cp(n) if n else None

    def put_node(self, node: Node) -> None:
        with self._lock:
            old = self._nodes.get(node.id)
            if old and old.parent_id != node.parent_id:
                self._children.get(old.parent_id, set()).discard(node.id)
            self._nodes[node.id] = _cp(node)
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
            return [_cp(n) for n in self._nodes.values()]

    def children(self, parent_id: str) -> list[Node]:
        with self._lock:
            return [_cp(self._nodes[c]) for c in self._children.get(parent_id, set())
                    if c in self._nodes]

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
            e = self._edges.get(edge_id)
            return _cp(e) if e else None

    def put_edge(self, edge: SecondaryEdge) -> None:
        with self._lock:
            self._edges[edge.id] = _cp(edge)

    def delete_edge(self, edge_id: str) -> None:
        with self._lock:
            self._edges.pop(edge_id, None)

    def edges_from(self, node_id, current_only=True):
        with self._lock:
            return [_cp(e) for e in self._edges.values()
                    if e.source_id == node_id and (e.is_current or not current_only)]

    def edges_to(self, node_id, current_only=True):
        with self._lock:
            out = [e for e in self._edges.values()
                   if e.target_id == node_id and (e.is_current or not current_only)]
            out += [e for e in self._edges.values()      # undirected edges reach from either end
                    if not e.directed and e.source_id == node_id and (e.is_current or not current_only)]
            return [_cp(e) for e in out]

    def current_edges(self):
        with self._lock:
            return [_cp(e) for e in self._edges.values() if e.is_current]

    # --- mounts ---
    def put_mount(self, mount: MountLink) -> None:
        with self._lock:
            self._mounts[mount.id] = _cp(mount)

    def delete_mount(self, mount_id: str) -> None:
        with self._lock:
            self._mounts.pop(mount_id, None)

    def mounts_of(self, host_id: str) -> list[MountLink]:
        with self._lock:
            return [_cp(m) for m in self._mounts.values() if m.host_id == host_id]

    def mounted_at(self, node_id: str) -> list[MountLink]:
        with self._lock:
            return [_cp(m) for m in self._mounts.values() if m.node_id == node_id]

    # --- versioned update (mutates the stored object in place; callers hold copies) ---
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

    # --- persistence (JSON; keeps the backend dependency-free) ---
    def save(self, path: str | Path) -> None:
        with self._lock:
            data = {
                "nodes": [{**asdict(n), "type": n.type.value} for n in self._nodes.values()],
                "edges": [asdict(e) for e in self._edges.values()],
                "mounts": [asdict(m) for m in self._mounts.values()],
            }
        Path(path).write_text(json.dumps(data), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "MemoryStore":
        store = cls()
        p = Path(path)
        if not p.exists():
            return store
        data = json.loads(p.read_text(encoding="utf-8"))
        for d in data.get("nodes", []):
            d = dict(d)
            d["type"] = NodeType(d["type"])
            store.put_node(Node(**d))
        for d in data.get("edges", []):
            store.put_edge(SecondaryEdge(**d))
        for d in data.get("mounts", []):
            store.put_mount(MountLink(**d))
        return store
