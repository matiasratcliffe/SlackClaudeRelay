"""Neo4j backend.

Model: nodes are `:CtxNode` with a `type` property; primary tree edges are `(child)-[:CHILD_OF]->
(parent)`; secondary edges are **reified** as `(:CtxNode)-[:REL_FROM]->(:EdgeNode)-[:REL_TO]->
(:CtxNode)` so the edge embedding is covered by the native (HNSW) vector index — Neo4j's vector index
indexes node properties only. Optimistic concurrency uses a `version` property + compare-and-swap.

Requires `neo4j>=5.14` and Neo4j 5.11+ (native vector index). Not exercised in this build phase; the
Cypher is the spec for the backend.
"""

from __future__ import annotations

from collections.abc import Iterable

from ..model import Node, NodeType, SecondaryEdge
from .base import StorageBackend

_NODE_PROPS = ("id", "type", "title", "body", "parent_id", "embedding", "tags", "owner_agent_id",
               "source", "authority", "summary", "version", "created_at", "updated_at")
_EDGE_PROPS = ("id", "source_id", "target_id", "verb_tags", "directed", "edge_embedding", "weight",
               "authority", "owner_agent_id", "source", "version", "valid_from", "valid_to",
               "created_at")


class Neo4jStore(StorageBackend):
    def __init__(self, uri: str, user: str, password: str, *, dim: int = 256,
                 database: str = "neo4j") -> None:
        try:
            from neo4j import GraphDatabase
        except ImportError as exc:  # pragma: no cover
            raise ImportError("Neo4jStore needs the 'neo4j' package: pip install 'context-graph[neo4j]'") from exc
        self._driver = GraphDatabase.driver(uri, auth=(user, password))
        self._db = database
        self._dim = dim

    def _run(self, cypher: str, **params):
        with self._driver.session(database=self._db) as s:
            return list(s.run(cypher, **params))

    # --- lifecycle ---
    def init(self) -> None:
        self._run("CREATE CONSTRAINT ctx_id IF NOT EXISTS FOR (n:CtxNode) REQUIRE n.id IS UNIQUE")
        self._run("CREATE CONSTRAINT edge_id IF NOT EXISTS FOR (e:EdgeNode) REQUIRE e.id IS UNIQUE")
        self._run(
            "CREATE VECTOR INDEX node_embedding_idx IF NOT EXISTS FOR (n:CtxNode) ON (n.embedding) "
            "OPTIONS {indexConfig: {`vector.dimensions`: $d, `vector.similarity_function`: 'cosine'}}",
            d=self._dim)
        self._run(
            "CREATE VECTOR INDEX edge_embedding_idx IF NOT EXISTS FOR (e:EdgeNode) ON (e.embedding) "
            "OPTIONS {indexConfig: {`vector.dimensions`: $d, `vector.similarity_function`: 'cosine'}}",
            d=self._dim)

    def close(self) -> None:
        self._driver.close()

    # --- nodes ---
    def get_node(self, node_id):
        rows = self._run("MATCH (n:CtxNode {id:$id}) RETURN n", id=node_id)
        return _to_node(rows[0]["n"]) if rows else None

    def put_node(self, node: Node) -> None:
        props = {k: getattr(node, k) for k in _NODE_PROPS}
        props["type"] = node.type.value
        self._run("MERGE (n:CtxNode {id:$id}) SET n += $props", id=node.id, props=props)
        if node.parent_id:
            self._run(
                "MATCH (c:CtxNode {id:$cid}) OPTIONAL MATCH (c)-[r:CHILD_OF]->() DELETE r "
                "WITH c MATCH (p:CtxNode {id:$pid}) MERGE (c)-[:CHILD_OF]->(p)",
                cid=node.id, pid=node.parent_id)

    def delete_node(self, node_id: str) -> None:
        self._run("MATCH (n:CtxNode {id:$id}) DETACH DELETE n", id=node_id)

    def all_nodes(self) -> Iterable[Node]:
        return [_to_node(r["n"]) for r in self._run("MATCH (n:CtxNode) RETURN n")]

    def children(self, parent_id: str) -> list[Node]:
        rows = self._run("MATCH (c:CtxNode)-[:CHILD_OF]->(:CtxNode {id:$pid}) RETURN c", pid=parent_id)
        return [_to_node(r["c"]) for r in rows]

    def ancestors(self, node_id: str) -> list[str]:
        rows = self._run(
            "MATCH p=(n:CtxNode {id:$id})-[:CHILD_OF*]->(a:CtxNode) "
            "RETURN [x IN nodes(p) | x.id] AS ids ORDER BY length(p) DESC LIMIT 1", id=node_id)
        if not rows:
            return []
        ids = rows[0]["ids"][1:]      # drop the node itself
        return list(reversed(ids))    # root-first

    # --- edges (reified) ---
    def get_edge(self, edge_id):
        rows = self._run("MATCH (e:EdgeNode {id:$id}) RETURN e", id=edge_id)
        return _to_edge(rows[0]["e"]) if rows else None

    def put_edge(self, edge: SecondaryEdge) -> None:
        props = {k: getattr(edge, k) for k in _EDGE_PROPS}
        props = {k: v for k, v in props.items() if v is not None}   # omit null valid_to → current
        self._run(
            "MATCH (s:CtxNode {id:$sid}), (t:CtxNode {id:$tid}) "
            "MERGE (e:EdgeNode {id:$id}) SET e += $props "
            "MERGE (s)-[:REL_FROM]->(e) MERGE (e)-[:REL_TO]->(t)",
            sid=edge.source_id, tid=edge.target_id, id=edge.id, props=props)

    def delete_edge(self, edge_id: str) -> None:
        self._run("MATCH (e:EdgeNode {id:$id}) DETACH DELETE e", id=edge_id)

    def edges_from(self, node_id, current_only=True):
        cur = "AND e.valid_to IS NULL" if current_only else ""
        rows = self._run(
            f"MATCH (:CtxNode {{id:$id}})-[:REL_FROM]->(e:EdgeNode) WHERE true {cur} RETURN e",
            id=node_id)
        return [_to_edge(r["e"]) for r in rows]

    def edges_to(self, node_id, current_only=True):
        cur = "AND e.valid_to IS NULL" if current_only else ""
        rows = self._run(
            f"MATCH (e:EdgeNode)-[:REL_TO]->(:CtxNode {{id:$id}}) WHERE true {cur} "
            "AND (e.directed = true OR true) RETURN e", id=node_id)
        edges = [_to_edge(r["e"]) for r in rows]
        return [e for e in edges if e.target_id == node_id and not (not e.directed and e.source_id == node_id)]

    def current_edges(self):
        return [_to_edge(r["e"])
                for r in self._run("MATCH (e:EdgeNode) WHERE e.valid_to IS NULL RETURN e")]

    # --- versioned update ---
    def cas_update(self, kind, obj_id, expected_version, changes):
        label = "CtxNode" if kind == "node" else "EdgeNode"
        rows = self._run(
            f"MATCH (n:{label} {{id:$id}}) WHERE n.version = $ver "
            "SET n += $changes, n.version = n.version + 1 RETURN n.version AS v",
            id=obj_id, ver=expected_version, changes=changes)
        return bool(rows)

    # --- vector search ---
    def vector_search(self, embedding, k, kind="node"):
        idx = "node_embedding_idx" if kind == "node" else "edge_embedding_idx"
        rows = self._run(
            "CALL db.index.vector.queryNodes($idx, $k, $emb) YIELD node, score RETURN node.id AS id, score",
            idx=idx, k=k, emb=embedding)
        return [(r["id"], r["score"]) for r in rows]


def _to_node(rec) -> Node:
    d = dict(rec)
    d["type"] = NodeType(d.get("type", "note"))
    return Node(**{k: d.get(k) for k in _NODE_PROPS if k in d})


def _to_edge(rec) -> SecondaryEdge:
    d = dict(rec)
    return SecondaryEdge(**{k: d.get(k) for k in _EDGE_PROPS if k in d})
