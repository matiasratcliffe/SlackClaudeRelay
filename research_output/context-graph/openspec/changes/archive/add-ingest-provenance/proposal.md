# Change: add-ingest-provenance

## Why
Writes must be safe, deduplicated, provenance-stamped, and history-preserving.

## What changes
Add the write/ingest path: upsert + auto-embed, near-duplicate edge reinforcement,
append-and-supersede on conflicts with authority ranking, and a synchronous structural
contradiction heuristic. LLM adjudication is explicitly deferred.

## Impact
- New capability: `ingest-provenance`.
- New code: ingest methods on the `ContextGraph` facade (`graph.py`).
