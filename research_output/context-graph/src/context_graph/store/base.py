"""Backend-agnostic storage contract.

Domain logic depends only on this interface, never on a concrete store. `cas_update` powers
optimistic concurrency for secondary edges and node-content fields; `vector_search` returns
`[(id, score)]` best-first.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable

from ..model import MountLink, Node, SecondaryEdge


class StorageBackend(ABC):
    # --- lifecycle ---
    def init(self) -> None:  # optional; e.g. create indexes
        ...

    def close(self) -> None:
        ...

    # --- nodes ---
    @abstractmethod
    def get_node(self, node_id: str) -> Node | None: ...

    @abstractmethod
    def put_node(self, node: Node) -> None: ...

    @abstractmethod
    def delete_node(self, node_id: str) -> None: ...

    @abstractmethod
    def all_nodes(self) -> Iterable[Node]: ...

    @abstractmethod
    def children(self, parent_id: str) -> list[Node]: ...

    def get_parent(self, node_id: str) -> str | None:
        n = self.get_node(node_id)
        return n.parent_id if n else None

    @abstractmethod
    def ancestors(self, node_id: str) -> list[str]:
        """Ancestor ids, root-first, excluding `node_id` itself."""

    # --- secondary edges ---
    @abstractmethod
    def get_edge(self, edge_id: str) -> SecondaryEdge | None: ...

    @abstractmethod
    def put_edge(self, edge: SecondaryEdge) -> None: ...

    @abstractmethod
    def delete_edge(self, edge_id: str) -> None: ...

    @abstractmethod
    def edges_from(self, node_id: str, current_only: bool = True) -> list[SecondaryEdge]: ...

    @abstractmethod
    def edges_to(self, node_id: str, current_only: bool = True) -> list[SecondaryEdge]: ...

    @abstractmethod
    def current_edges(self) -> list[SecondaryEdge]: ...

    # --- mount links (navigation-only multi-parent; ownership unchanged) ---
    @abstractmethod
    def put_mount(self, mount: MountLink) -> None: ...

    @abstractmethod
    def delete_mount(self, mount_id: str) -> None: ...

    @abstractmethod
    def mounts_of(self, host_id: str) -> list[MountLink]:
        """Mounts hosted under `host_id` (its grafted children)."""

    @abstractmethod
    def mounted_at(self, node_id: str) -> list[MountLink]:
        """Mounts that graft `node_id` elsewhere (its extra hierarchy positions)."""

    # --- versioned update (optimistic concurrency) ---
    @abstractmethod
    def cas_update(self, kind: str, obj_id: str, expected_version: int, changes: dict) -> bool:
        """Apply `changes` iff current version == expected_version; bump version. `kind`: node|edge."""

    # --- vector search ---
    @abstractmethod
    def vector_search(self, embedding: list[float], k: int, kind: str = "node") -> list[tuple[str, float]]:
        """Top-k `(id, score)` by embedding similarity. `kind`: node|edge."""
