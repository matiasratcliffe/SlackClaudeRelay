# ingest-provenance Specification

## Purpose
Write nodes and edges through the lock manager with auto-embedding, near-duplicate reinforcement,
append-and-supersede provenance, and a synchronous structural contradiction heuristic.

## Requirements

### Requirement: Write API with auto-embed
The system SHALL upsert nodes/edges by id, auto-embed content on write, stamp provenance
(`source`, `owner_agent_id`, authority rank), and route all writes through the lock manager.

#### Scenario: Auto-embed on create
- **WHEN** a node is created without an embedding
- **THEN** its embedding is computed from its content before storage.

### Requirement: Dedup / reinforce edges
The system SHALL detect a new secondary edge near-identical to an existing edge between the same
endpoints and reinforce it (bump weight, refresh timestamp) instead of duplicating.

#### Scenario: Duplicate edge reinforces
- **WHEN** an edge equivalent to an existing one is added
- **THEN** the existing edge's weight increases and no duplicate is stored.

### Requirement: Append-and-supersede
The system SHALL, on conflicting facts, close the old edge (`valid_to`) and append a new one,
preserving history, ordered by authority (user-stated > system-of-record > direct inference >
chained inference).

#### Scenario: Superseding fact
- **WHEN** a higher-authority fact conflicts with an existing one
- **THEN** the old edge is marked invalid-from-now and the new edge becomes current.

### Requirement: Structural contradiction heuristic
The system SHALL flag as a candidate contradiction any two current edges with the same subject and
the same *functional* relation but different objects (functional vs multivalued verbs are declared,
not inferred). LLM adjudication is out of scope.

#### Scenario: Functional-relation conflict flagged
- **WHEN** two current edges assert a functional relation from one node to different targets
- **THEN** the pair is flagged as a candidate contradiction for later review.
