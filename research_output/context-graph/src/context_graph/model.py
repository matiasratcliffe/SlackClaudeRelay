"""Core data model: ownership-tree nodes and first-class secondary edges.

The primary (parent) edges form a strict single-parent, single-root, acyclic tree that encodes
*ownership* and lock scope only — never meaning. All relationships live on `SecondaryEdge`s, which
may connect any two nodes and carry their own embedding, verb tags, weight, and validity window.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum

ROOT_ID = "root"


class NodeType(str, Enum):
    ROOT = "root"
    SECTION = "section"      # a life-section subtree (work / personal / ideas / ...)
    PERSON = "person"
    PROJECT = "project"
    FACT = "fact"
    NOTE = "note"
    SKILL = "skill"         # guidance/behaviour, kept distinct from pure context (note 2)


def new_id() -> str:
    """Short, collision-resistant id."""
    return uuid.uuid4().hex[:12]


def _now() -> float:
    return time.time()


@dataclass
class Node:
    """A unit of context/knowledge owned by exactly one parent (root owns itself)."""

    title: str
    type: NodeType = NodeType.NOTE
    body: str = ""
    parent_id: str | None = None
    id: str = field(default_factory=new_id)
    embedding: list[float] | None = None
    tags: list[str] = field(default_factory=list)
    owner_agent_id: str | None = None
    source: str | None = None
    authority: int = 0          # provenance rank; see graph.Authority
    summary: str | None = None  # rolled-up hub summary (populated lazily; out of scope to regen)
    version: int = 1
    created_at: float = field(default_factory=_now)
    updated_at: float = field(default_factory=_now)


@dataclass
class SecondaryEdge:
    """A directed-or-symmetric semantic relationship between any two nodes.

    Secondary edges are traversal *wormholes* — their job is to justify hopping to an otherwise
    unrelated part of the graph — so they carry more information than primary edges: endpoint
    embedding `similarity`, ownership-tree `tree_distance` (a wormhole is worth more the farther
    apart its endpoints sit in the hierarchy), and a free-text `rationale`.
    """

    source_id: str
    target_id: str
    verb_tags: list[str] = field(default_factory=list)
    directed: bool = True
    id: str = field(default_factory=new_id)
    edge_embedding: list[float] | None = None
    weight: float = 1.0
    similarity: float | None = None       # cosine of endpoint node embeddings at link time
    tree_distance: int | None = None      # hops between endpoints via the ownership tree
    rationale: str | None = None          # why this hop is useful (agent- or human-authored)
    authority: int = 0
    owner_agent_id: str | None = None
    source: str | None = None
    version: int = 1
    valid_from: float = field(default_factory=_now)
    valid_to: float | None = None    # None = currently valid
    created_at: float = field(default_factory=_now)

    @property
    def is_current(self) -> bool:
        return self.valid_to is None


@dataclass
class MountLink:
    """Grafts a node into a second hierarchy position WITHOUT transferring ownership.

    The filesystem-symlink analog: `node_id` keeps its single ownership parent (locks, authority),
    but appears under `host_id` for navigation, traversal, and export. This is how e.g.
    `work/team` primary-links teammates whose owning subtree is `social`.
    """

    host_id: str
    node_id: str
    id: str = field(default_factory=new_id)
    label: str | None = None
    created_at: float = field(default_factory=_now)


# --- Tree invariants (pure; reused by every backend) --------------------------------

def validate_new_node(node: Node, exists) -> None:
    """Raise ValueError if `node` violates tree rules. `exists(id)->bool` checks a parent exists."""
    if node.type == NodeType.ROOT or node.id == ROOT_ID:
        if node.parent_id is not None:
            raise ValueError("root node must not have a parent")
        return
    if not node.parent_id:
        raise ValueError("non-root node requires a parent_id")
    if not exists(node.parent_id):
        raise ValueError(f"parent {node.parent_id!r} does not exist")


def would_create_cycle(node_id: str, new_parent_id: str, get_parent) -> bool:
    """True if re-parenting `node_id` under `new_parent_id` would form a cycle.

    `get_parent(id)->str|None` returns a node's current parent.
    """
    if node_id == new_parent_id:
        return True
    cur: str | None = new_parent_id
    seen: set[str] = set()
    while cur is not None and cur not in seen:
        if cur == node_id:
            return True
        seen.add(cur)
        cur = get_parent(cur)
    return False
