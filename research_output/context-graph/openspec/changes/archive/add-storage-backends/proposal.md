# Change: add-storage-backends

## Why
Domain logic must not bind to a concrete store; the tool must run with no server yet target Neo4j.

## What changes
Define `StorageBackend`, implement a zero-dep in-memory reference backend (brute-force vector
search) and a Neo4j backend (labels, `:CHILD_OF`, reified `:EdgeNode`, HNSW vector index).

## Impact
- New capability: `storage`.
- New code: `store/base.py`, `store/memory_store.py`, `store/neo4j_store.py`.
