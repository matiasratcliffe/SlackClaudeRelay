# concurrency-locking Specification

## Purpose
Let many agents share one graph safely: hierarchical intent locks on the ownership tree and
optimistic concurrency on secondary edges, all keyed by agent id.

## Requirements

### Requirement: Hierarchical intent locks (tree)
The system SHALL, for a write to a tree node, acquire intent-exclusive (IX) locks on every ancestor
and an exclusive (X) lock on the target, so agents writing in disjoint subtrees never contend.

#### Scenario: Disjoint subtrees do not contend
- **WHEN** agent A writes under `work/` and agent B writes under `personal/`
- **THEN** both acquire their locks without blocking each other.

#### Scenario: Conflicting exclusive write blocks
- **WHEN** agent B requests an X lock on a node A already holds X on
- **THEN** B is refused (or waits) with a clear conflict error.

### Requirement: Optimistic concurrency (secondary edges)
The system SHALL update secondary edges and node-content fields by compare-and-swap on a `version`,
retrying losers against fresh state, rather than locking.

#### Scenario: Stale write loses
- **WHEN** two agents update the same edge and one commits first
- **THEN** the second's CAS fails and it must retry against the new version.

### Requirement: Agent-id keying and safe release
The system SHALL track locks per `agent_id`, detect an agent re-entering its own lock, and release
all of an agent's locks on explicit release or crash/expiry.

#### Scenario: Release on crash
- **WHEN** an agent holding locks disconnects and its lease expires
- **THEN** its locks are released without blocking others.
