# storage Specification

## Purpose
Provide a backend-agnostic storage contract for nodes, secondary edges, versioned updates, and
vector search, with an in-memory reference backend and a Neo4j backend.

## Requirements

### Requirement: Storage interface
The system SHALL define a `StorageBackend` interface covering node/edge CRUD, child listing,
ancestor-path lookup, versioned (compare-and-swap) updates, and vector search, such that domain
logic never depends on a concrete backend.

#### Scenario: Swap backends via config
- **WHEN** the configured backend changes between in-memory and Neo4j
- **THEN** the same domain operations succeed against either without code changes.

### Requirement: In-memory reference backend
The system SHALL provide a zero-dependency in-memory backend implementing the full interface,
including brute-force cosine vector search, serving as the executable reference semantics.

#### Scenario: Runs with no server
- **WHEN** the tool is used with the in-memory backend
- **THEN** all operations work with no external service or credentials.

### Requirement: Neo4j backend
The system SHALL provide a Neo4j backend using `:CtxNode` (+ subtype) labels, `:CHILD_OF` primary
edges, reified `:EdgeNode` for secondary edges (so edge embeddings are index-able), and a native
HNSW vector index.

#### Scenario: Edge embedding is indexable
- **WHEN** a secondary edge with an embedding is stored in Neo4j
- **THEN** it is reified as an `:EdgeNode` whose embedding is covered by the vector index.
