# graph-model Specification

## Purpose
Define the graph's units: context/knowledge **nodes** arranged in a strict single-parent **ownership
tree**, and first-class **secondary semantic edges** that connect any two nodes. The tree carries
ownership/lock-scope only; meaning lives on secondary edges.

## Requirements

### Requirement: Node
The system SHALL represent each unit of context as a node with a stable `id`, a `type` (subtype such
as `person`/`project`/`fact`/`note`/`skill`/`root`), `title`, `body`, optional `embedding`, `tags`,
timestamps, `owner_agent_id`, and exactly one `parent_id` (except the root).

#### Scenario: Create a node under a parent
- **WHEN** a node is created with a valid existing `parent_id`
- **THEN** it is stored with a generated `id`, timestamps set, and appears as a child of that parent.

#### Scenario: Reject a node with no parent that is not root
- **WHEN** a non-root node is created without a `parent_id`
- **THEN** creation is rejected with a validation error.

### Requirement: Single-parent acyclic tree
The system SHALL enforce that primary (parent) edges form a single-rooted, acyclic, single-parent
tree.

#### Scenario: Reject a cycle
- **WHEN** a node's `parent_id` is changed to one of its own descendants
- **THEN** the change is rejected as it would create a cycle.

#### Scenario: Single root
- **WHEN** the graph is initialized
- **THEN** exactly one `root` node exists and it has no parent.

### Requirement: Secondary edge
The system SHALL represent any-to-any relationships as first-class secondary edges with `id`,
`source_id`, `target_id`, `directed` flag, optional `edge_embedding`, `verb_tags`, `weight`,
`version`, and validity window (`valid_from`/`valid_to`). As traversal wormholes, they SHALL also
carry endpoint embedding `similarity`, ownership-tree `tree_distance` (both computed at link time),
and an optional free-text `rationale`.

#### Scenario: Link two arbitrary nodes
- **WHEN** a secondary edge is created between two existing nodes in any subtrees
- **THEN** it is stored as an independent record without altering either node's parent.

#### Scenario: Meaning does not use the tree
- **WHEN** a hierarchical-feeling relationship (e.g. task belongs to project) is recorded
- **THEN** it is stored as a secondary edge, not as a parent change.

#### Scenario: Wormhole context is captured
- **WHEN** a secondary edge is created between two embedded nodes
- **THEN** the edge stores their embedding similarity and their hop distance through the ownership
  tree.

### Requirement: Mount links
The system SHALL support mount links that graft a node under an additional hierarchy host for
navigation, WITHOUT changing the node's ownership parent or lock scope. Mounts SHALL be idempotent
per (host, node); self-mounts and mounting under the node's own parent SHALL be rejected.

#### Scenario: Teammate mounted under Team
- **WHEN** a person owned by `social` is mounted under `work-team`
- **THEN** traversal reaches the person from the work side, while their `parent_id` and lock
  ancestry remain in `social`.

#### Scenario: Duplicate mount collapses
- **WHEN** the same (host, node) mount is requested twice
- **THEN** the existing mount is returned and no duplicate is created.
