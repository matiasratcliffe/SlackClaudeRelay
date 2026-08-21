# Design — add-storage-backends

- `StorageBackend` = `abc.ABC`; methods raise `NotImplementedError`.
- `cas_update(kind, id, expected_version, changes)` → bool (False = version mismatch → caller retry).
- `vector_search(embedding, k, kind)` returns `[(id, score)]`; in-memory does brute-force cosine.
- In-memory: `dict[id,Node]`, `dict[id,SecondaryEdge]`, child index `dict[parent,set]`; thread-safe
  via a single `RLock` (lock *manager* handles semantics; store lock only guards structure).
- Neo4j: driver sessions; MERGE nodes by id; `:CHILD_OF` (child→parent); secondary edge reified as
  `(:CtxNode)-[:FROM]->(:EdgeNode)<-[:TO]-(:CtxNode)`; vector index created on first init.
- Neo4j methods documented with the exact Cypher (see RESEARCH-DIGEST §5); not executed this phase.
