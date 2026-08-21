# embeddings-entrypoints Specification

## Purpose
Turn text into vectors via a pluggable provider (with an offline fallback) and find traversal
**entry points** by semantic similarity using a relative cutoff.

## Requirements

### Requirement: Embedding provider
The system SHALL define an `EmbeddingProvider` interface and ship an offline, deterministic default
so embeddings work with no network or API key.

#### Scenario: Deterministic offline embedding
- **WHEN** the default provider embeds the same text twice
- **THEN** it returns identical vectors of a fixed dimension.

### Requirement: Entry-point search
The system SHALL return, for a query, the nodes whose embeddings are nearest, selected by a
**relative cutoff** (within a margin of the top match or above a floor) rather than a fixed top-K.

#### Scenario: Single strong match
- **WHEN** one node is far closer to the query than the rest
- **THEN** only that node (and any within the margin) is returned as a seed.

#### Scenario: Multi-cluster query
- **WHEN** two separate clusters match comparably
- **THEN** seeds from both clusters are returned.

### Requirement: Hybrid ranking
The system SHALL combine vector similarity with tag/label matching when ranking entry points.

#### Scenario: Tag boosts a match
- **WHEN** two nodes have equal similarity but one matches a query tag
- **THEN** the tag-matching node ranks higher.
