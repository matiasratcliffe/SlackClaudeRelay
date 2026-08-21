# Change: iteration-1-hardening

## Why (self-grill of the first build)
Grilling the initial build surfaced three genuine, in-scope gaps (not scope creep, not pi):
1. **Ephemeral memory store.** The in-memory backend is process-local, so CLI `add-node`/`link`
   don't persist across invocations — the tool isn't actually usable standalone without Neo4j.
2. **Hub summaries specced but stubbed.** D8/§3 of the research call for hub-summary-first traversal;
   the model has a `summary` field and assembly reads it, but nothing populates it.
3. **No executable tests.** A spec-driven project should encode its scenarios as tests to prevent
   regressions and to prove the reference semantics.

Rejected (out of scope / "going wild"): Leiden community re-filing tool, async contradiction LLM
resolution, round-trip Obsidian import — left as backlog.

## What changes
- `MemoryStore` JSON save/load; CLI `--db <path>` persists memory-backend state across runs.
- `ContextGraph.recompute_hub_summaries(degree_threshold)` rolls up high-degree nodes.
- A `pytest` suite covering model invariants, entry points, traversal, locking, ingest, export.

## Impact
- Modifies capabilities: `storage`, `traversal-assembly` (summary), `cli`.
- New: `tests/`.
