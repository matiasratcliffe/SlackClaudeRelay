# Design — add-concurrency-locking

- `LockManager` holds `path -> {mode, agents, lease_expiry}`; modes `IX`, `X` (read = `IS`/shared,
  compatible). Compatibility matrix: IX+IX ok, IX+IS ok, X excludes all others.
- `acquire_write(agent_id, path, ttl)`: compute ancestor paths from `ancestors()`, take IX on each,
  X on target; on conflict raise `LockConflict`. Re-entrancy: same agent_id on a held lock is a
  no-op count bump.
- Leases: `lease_expiry` timestamp; `sweep()` releases expired; `release_all(agent_id)` on
  disconnect.
- Edge concurrency is not lock-based: `cas_update` on the store's `version`; `LockManager` exposes a
  `retry(fn, attempts)` helper for CAS loops.
- Backend-agnostic (in-memory dict now; Neo4j would back it with a locks table / `apoc.lock.nodes`).
- Deadlock-free by construction: locks acquired root→leaf in a fixed order.
