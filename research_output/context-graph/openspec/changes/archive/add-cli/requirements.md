# Requirements (EARS) — add-cli

## User story
As a user, I want to drive the graph from the terminal and try it instantly.

## Requirements
- R1. The system SHALL provide `init`, `add-node`, `link`, `search`, `traverse`, `export`,
  `lock-status`, `demo`, each with `--json`.
- R2. WHEN `search "<q>"` runs, the system SHALL print ranked entry points.
- R3. WHEN `traverse "<q>" --budget N` runs, the system SHALL print the assembled context + included
  nodes/edges.
- R4. WHEN `demo` runs on a clean environment, the system SHALL load a sample graph via the in-memory
  backend + offline embeddings with no credentials.

## Acceptance criteria
- `demo` then `search`/`traverse` work with no external service.
- `--json` yields machine-readable output for each command.
