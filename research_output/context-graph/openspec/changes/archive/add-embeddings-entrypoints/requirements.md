# Requirements (EARS) — add-embeddings-entrypoints

## User story
As an agent, I need to find where to start in the graph from a natural-language query.

## Requirements
- R1. The system SHALL define `EmbeddingProvider.embed(text) -> vector` and ship an offline
  deterministic default of fixed dimension.
- R2. WHEN embedding identical text twice, the default provider SHALL return identical vectors.
- R3. WHEN searching entry points, the system SHALL select seeds by a relative cutoff (margin from
  top match or absolute floor), not a fixed K.
- R4. WHERE query tags match a node's tags, the system SHALL boost that node's rank.
- R5. WHEN candidates span multiple top-level subtrees, the system SHALL return seeds from each
  matching cluster.

## Acceptance criteria
- Single dominant match returns one seed; balanced two-cluster query returns seeds from both.
- Tag match breaks ties upward.
