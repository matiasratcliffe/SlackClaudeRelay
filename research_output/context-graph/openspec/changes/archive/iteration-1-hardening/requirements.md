# Requirements (EARS) — iteration-1-hardening

## Requirements
- R1. WHEN the memory backend is used with a `--db` path, the system SHALL persist nodes and edges
  to that path and reload them on the next run.
- R2. WHEN `recompute_hub_summaries(threshold)` runs, the system SHALL set a rolled-up `summary` on
  every node whose degree ≥ threshold, listing its top relations.
- R3. WHILE traversing, the system SHALL prefer a node's `summary` over its raw body when present
  (already true; covered by test).
- R4. The system SHALL ship tests encoding the core scenarios of every capability.

## Acceptance criteria
- Save then reload round-trips the sample graph identically.
- A hub above threshold gains a non-empty summary; assembly renders it.
- `pytest` passes.
