# Requirements (EARS) — add-concurrency-locking

## User story
As one of many agents, I need safe concurrent writes so shared memory stays consistent.

## Requirements
- R1. WHEN an agent writes a tree node, the system SHALL take IX on all ancestors and X on the
  target.
- R2. WHILE agents write in disjoint subtrees, the system SHALL NOT make them contend.
- R3. IF an agent requests X on a node another agent holds X on, THEN the system SHALL refuse with a
  conflict error.
- R4. WHEN an agent re-requests a lock it already holds, the system SHALL treat it as re-entrant.
- R5. WHEN updating a secondary edge, the system SHALL use version CAS and fail stale writers.
- R6. WHEN an agent's lease expires or it releases, the system SHALL free all its locks.

## Acceptance criteria
- Disjoint-subtree writes both succeed; same-node X conflict raises.
- Stale edge CAS returns failure; re-entrant acquire succeeds.
