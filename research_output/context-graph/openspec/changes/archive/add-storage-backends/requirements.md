# Requirements (EARS) — add-storage-backends

## User story
As a developer, I need a swappable storage contract so I can run locally with no dependencies and
scale to Neo4j unchanged.

## Requirements
- R1. The system SHALL define `StorageBackend` with node/edge CRUD, `children`, `ancestors`,
  `cas_update`, and `vector_search`.
- R2. WHEN configured for in-memory, the system SHALL satisfy the full interface with no external
  service.
- R3. WHEN configured for Neo4j, the system SHALL store nodes as `:CtxNode`, primary edges as
  `:CHILD_OF`, and secondary edges reified as `:EdgeNode`.
- R4. WHERE a secondary edge has an embedding under Neo4j, the system SHALL make it index-able via
  the reified node.
- R5. WHEN two backends run the same operation sequence, they SHALL produce equivalent results.

## Acceptance criteria
- In-memory backend passes the storage-contract scenarios.
- Neo4j backend issues the documented Cypher (index creation, `db.index.vector.queryNodes`).
