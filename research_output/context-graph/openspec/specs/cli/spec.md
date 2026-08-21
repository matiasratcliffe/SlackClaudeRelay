# cli Specification

## Purpose
Expose the graph from the terminal for humans and scripts, self-contained by default (in-memory
store + offline embeddings + a seeded sample graph).

## Requirements

### Requirement: Core commands
The system SHALL provide `init` (with `--structure free|opinionated`), `add-node`, `link`, `mount`,
`search`, `traverse`, `export`, `summarize`, `lock-status`, and `demo`, each with human-readable
output and a `--json` option, plus `--db` persistence for the memory backend and `--agent` identity.

#### Scenario: Search returns entry points
- **WHEN** `search "<query>"` runs
- **THEN** it prints the ranked entry-point nodes (or JSON with `--json`).

#### Scenario: Traverse assembles context
- **WHEN** `traverse "<query>" --budget N` runs
- **THEN** it prints the assembled context blob and the nodes/edges included.

### Requirement: Self-contained demo
The system SHALL provide `demo` that loads a seeded sample graph using the in-memory backend and
offline embeddings, requiring no external service.

#### Scenario: Demo with no setup
- **WHEN** `demo` runs on a clean environment
- **THEN** a sample graph is loaded and a sample search/traverse works without any credentials.
