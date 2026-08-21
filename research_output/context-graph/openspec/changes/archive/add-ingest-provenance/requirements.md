# Requirements (EARS) — add-ingest-provenance

## User story
As an agent, I need to record knowledge that stays consistent, traceable, and non-destructive.

## Requirements
- R1. WHEN a node/edge is written, the system SHALL upsert by id, auto-embed missing embeddings, and
  stamp `source`, `owner_agent_id`, and authority rank.
- R2. WHEN a new edge is near-identical to an existing edge between the same endpoints, the system
  SHALL reinforce it (bump weight, refresh timestamp) instead of duplicating.
- R3. WHEN a higher-authority fact conflicts with a current one, the system SHALL close the old edge
  (`valid_to`) and append the new one.
- R4. WHEN two current edges share subject and a functional relation but differ in object, the
  system SHALL flag a candidate contradiction.
- R5. All writes SHALL pass through the lock manager.

## Acceptance criteria
- Duplicate edge reinforces; superseding fact preserves history; functional conflict is flagged.
- Authority order: user-stated > system-of-record > direct inference > chained inference.
