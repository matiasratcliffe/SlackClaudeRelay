# Design — iteration-1-hardening

- **Persistence:** `MemoryStore.save(path)` / `load(path)` (classmethod) serialize nodes+edges to
  JSON via dataclass `asdict`, restoring `NodeType`. CLI gains `--db`; when set with the memory
  backend, load on start (if the file exists) and save after mutating commands. Keeps the store
  dependency-free.
- **Hub summaries:** `ContextGraph.recompute_hub_summaries(threshold)` computes degree =
  `len(edges_from)+len(edges_to)`; for hubs it writes a summary like
  `"<title> — hub of N relations: works_on→…, mentors→…"` (top few by weight) via `cas_update`.
  Assembly already prefers `summary`; no change needed there.
- **Tests:** `tests/` with one file per capability area; use the in-memory backend + `HashingEmbedder`
  only (no network, no Neo4j). Neo4j backend is import-checked but not run.
