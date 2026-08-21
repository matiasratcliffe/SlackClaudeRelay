# Requirements (EARS) — add-graph-model

## User story
As an agent sharing long-term memory, I need a well-defined node/edge model so context is stored
consistently and relationships aren't forced into the hierarchy.

## Requirements
- R1. WHEN a node is created with a valid `parent_id`, the system SHALL persist it with a generated
  id and timestamps.
- R2. IF a non-root node is created without a `parent_id`, THEN the system SHALL reject it.
- R3. WHILE maintaining the tree, the system SHALL ensure exactly one root and single-parent,
  acyclic primary edges.
- R4. WHEN a `parent_id` change would create a cycle, the system SHALL reject it.
- R5. WHEN any relationship (including hierarchical-feeling ones) is recorded, the system SHALL store
  it as a secondary edge, not a parent change.
- R6. WHERE an edge is provided, the system SHALL persist `verb_tags`, `weight`, `directed`,
  `version`, and validity window as first-class fields.

## Acceptance criteria
- Creating a valid node and a valid edge round-trips all fields.
- Cycle, missing-parent, and multi-root attempts raise validation errors.
