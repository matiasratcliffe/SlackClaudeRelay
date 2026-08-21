# structure-templates Specification

## Purpose
Deploy the graph with a known shape: `free` (bare root) or `opinionated` — the hardcoded macro-node
taxonomy with fixed ids and hardcoded descriptions, so every agent and skill addresses the same
sections deterministically on any deployment.

## Requirements

### Requirement: Opinionated deployment
The system SHALL provide a hardcoded taxonomy (`preferences`, `skills`, `work` + `work-facts` +
`work-team` + `work-projects`, `personal` + `personal-facts` + `personal-org`, `social`, `ideas`),
each node created with a **fixed id**, section type, tags, and a hardcoded description body defined
in code.

#### Scenario: Deterministic sections
- **WHEN** `deploy_structure(g, "opinionated")` runs on a fresh graph
- **THEN** every macro node exists at its fixed id with a non-empty description.

#### Scenario: Idempotent redeploy
- **WHEN** the opinionated deployment runs again
- **THEN** existing nodes are untouched and nothing new is created.

### Requirement: Free mode
The system SHALL default to `free` mode, creating only the root node.

#### Scenario: Bare root
- **WHEN** `deploy_structure(g, "free")` runs
- **THEN** only the root exists.

### Requirement: Canonical people placement
The taxonomy SHALL designate `social` as the sole owner of person nodes; other sections reference
people via mounts (e.g. `work-team`) or secondary edges, never copies.

#### Scenario: Team references, social owns
- **WHEN** a teammate is added
- **THEN** their node is owned by `social` and mounted under `work-team`.
