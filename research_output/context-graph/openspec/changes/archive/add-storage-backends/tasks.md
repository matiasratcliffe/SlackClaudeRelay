# Tasks — add-storage-backends

- [x] Define `StorageBackend` ABC (CRUD, children, ancestors, cas_update, vector_search).
- [x] Implement `MemoryStore` incl. brute-force cosine `vector_search`.
- [x] Implement `Neo4jStore` (labels, `:CHILD_OF`, reified `:EdgeNode`, vector index Cypher).
- [x] Fold requirements into `specs/storage/spec.md`.
