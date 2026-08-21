# Change: add-concurrency-locking

## Why
Many agents must share one graph without corrupting it or serializing on hubs.

## What changes
Add a `LockManager`: hierarchical intent locks (IX/X) on the ownership tree and optimistic
version/CAS on secondary edges, all keyed by agent id, with lease-based release.

## Impact
- New capability: `concurrency-locking`.
- New code: `locking.py`; consumed by the write/ingest path.
