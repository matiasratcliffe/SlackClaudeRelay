# Requirements (EARS) — iteration-2-shared-truth

## User story
As the owner of many agents, I want one graph they all share — deployed with a known structure,
navigable across life-sections, with wormhole edges rich enough to justify a hop — usable by humans
and agents through the same interface.

## Requirements
- R1. WHEN `init --structure opinionated` runs, the system SHALL create the hardcoded macro nodes
  (preferences, skills, work + work-facts + work-team + work-projects, personal + personal-facts +
  personal-org, social, ideas) with **fixed ids** and their hardcoded descriptions.
- R2. WHEN `init --structure free` runs (default), the system SHALL create only the root.
- R3. WHEN a node is mounted under a host, the system SHALL keep its ownership parent unchanged and
  SHALL NOT change lock scope; the mount is navigation only.
- R4. WHILE traversing or exporting, the system SHALL treat mounts as hierarchy (traversal expands
  through them; export lists them under the host).
- R5. IF a mount would duplicate an existing (host, node) pair or mount a node into itself/its own
  ownership position, THEN the system SHALL reject or return the existing mount.
- R6. WHEN a secondary edge is created, the system SHALL compute and store the endpoints' embedding
  `similarity` and ownership-tree `tree_distance`, and accept an optional `rationale`.
- R7. WHEN assembling context, the system SHALL surface each rendered edge's tree distance.
- R8. The system SHALL document one common human/agent contract (INTERFACE.md) covering the CLI and
  facade with the deterministic macro ids and write-etiquette (what belongs in which section).

## Acceptance criteria
- Opinionated init yields all macro ids with non-empty descriptions; free init yields root only.
- A teammate owned by `social` mounted under `work-team` is reachable via traversal from work, and
  its locks still key off the social subtree.
- New edges carry similarity + tree_distance; duplicate mounts are not duplicated.
- pytest green.
